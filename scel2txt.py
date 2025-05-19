"""
搜狗细胞词库转鼠须管（Rime）词库

搜狗的 scel 词库是按照一定格式保存的 Unicode 编码文件，其中每两个字节表示一个字符（中文汉字或者英文字母），主要两部分:

1. 全局拼音表，在文件中的偏移值是 0x1540+4, 格式为 (py_idx, py_len, py_str)
    - py_idx: 两个字节的整数，代表这个拼音的索引
    - py_len: 两个字节的整数，拼音的字节长度
    - py_str: 当前的拼音，每个字符两个字节，总长 py_len

2. 汉语词组表，在文件中的偏移值是 0x2628 或 0x26c4, 格式为 (word_count, py_idx_count, py_idx_data, (word_len, word_str, ext_len, ext){word_count})，其中 (word_len, word, ext_len, ext){word_count} 一共重复 word_count 次, 表示拼音的相同的词一共有 word_count 个
    - word_count: 两个字节的整数，同音词数量
    - py_idx_count:  两个字节的整数，拼音的索引个数
    - py_idx_data: 两个字节表示一个整数，每个整数代表一个拼音的索引，拼音索引数 
    - word_len:两个字节的整数，代表中文词组字节数长度
    - word_str: 汉语词组，每个中文汉字两个字节，总长度 word_len
    - ext_len: 两个字节的整数，可能代表扩展信息的长度，好像都是 10
    - ext: 扩展信息，一共 10 个字节，前两个字节是一个整数(不知道是不是词频)，后八个字节全是 0，ext_len 和 ext 一共 12 个字节

参考资料 
1. https://raw.githubusercontent.com/archerhu/scel2mmseg/master/scel2mmseg.py
2. https://raw.githubusercontent.com/xwzhong/small-program/master/scel-to-txt/scel2txt.py
"""
import struct
import os
import sys


def read_utf16_str(f, offset=-1, len=2):
    if offset >= 0:
        f.seek(offset)
    string = f.read(len)
    return string.decode('UTF-16LE')


def read_uint16(f):
    return struct.unpack('<H', f.read(2))[0]


def get_hz_offset(f, filename):
    try:
        header = f.read(128)
        if len(header) < 128:
            error_msg = f"错误：文件太小，不是有效的搜狗词库文件: {filename}"
            print(error_msg)
            with open("error.log", "a", encoding="utf-8") as log:
                log.write(error_msg + "\n")
            return None
            
        mask = header[4]
        print(f"文件标识值: 0x{mask:02x} (文件: {filename})")
        
        if mask == 0x44:
            return 0x2628
        elif mask == 0x45:
            return 0x26c4
        else:
            error_msg = f"错误：不支持的文件类型(文件标识: 0x{mask:02x}): {filename}\n有效的文件标识应该是 0x44 或 0x45"
            print(error_msg)
            with open("error.log", "a", encoding="utf-8") as log:
                log.write(error_msg + "\n")
            return None
    except Exception as e:
        error_msg = f"读取文件时发生错误: {filename}\n详细信息: {str(e)}"
        print(error_msg)
        with open("error.log", "a", encoding="utf-8") as log:
            log.write(error_msg + "\n")
        return None

def get_words_from_sogou_cell_dict(fname):
    with open(fname, 'rb') as f:
        hz_offset = get_hz_offset(f, fname)
        if hz_offset is None:
            return []
        
        try:
            (title, category, desc, samples) = get_dict_meta(f)
            py_map = get_py_map(f)
            file_size = os.path.getsize(fname)
            words = get_records(f, file_size, hz_offset, py_map)
            return words
        except Exception as e:
            error_msg = f"处理文件时发生错误: {fname}\n详细信息: {str(e)}"
            print(error_msg)
            with open("error.log", "a", encoding="utf-8") as log:
                log.write(error_msg + "\n")
            return []


def get_dict_meta(f):
    title = read_utf16_str(f, 0x130, 0x338 - 0x130)
    category = read_utf16_str(f, 0x338, 0x540 - 0x338)
    desc = read_utf16_str(f, 0x540, 0xd40 - 0x540)
    samples = read_utf16_str(f, 0xd40, 0x1540 - 0xd40)
    return title, category, desc, samples


def get_py_map(f):
    py_map = {}
    f.seek(0x1540+4)

    while True:
        py_idx = read_uint16(f)
        py_len = read_uint16(f)
        py_str = read_utf16_str(f, -1, py_len)

        if py_idx not in py_map:
            py_map[py_idx] = py_str

        # 如果拼音为 zuo，说明是最后一个了
        if py_str == 'zuo':
            break
    return py_map


def get_records(f, file_size, hz_offset, py_map):
    f.seek(hz_offset)
    records = []
    try:
        while f.tell() != file_size:
            try:
                word_count = read_uint16(f)
                py_idx_count = int(read_uint16(f) / 2)

                py_set = []
                for i in range(py_idx_count):
                    py_idx = read_uint16(f)
                    if (py_map.get(py_idx, None) == None):
                        return records
                    py_set.append(py_map[py_idx])
                py_str = " ".join(py_set)

                for i in range(word_count):
                    word_len = read_uint16(f)
                    word_str = read_utf16_str(f, -1, word_len)

                    # 跳过 ext_len 和 ext 共 12 个字节
                    f.read(12)
                    records.append((py_str, word_str))
            except struct.error:
                # 如果读取过程中遇到文件结尾，直接返回已收集的记录
                return records
    except:
        # 如果发生任何其他错误，返回已收集的记录
        return records
    return records


def save(records, f):
    records_translated = list(map(lambda x: "%s\t%s" % (
        x[1], x[0]), records))
    f.write("\n".join(records_translated))
    return records_translated


def main():
    # 创建或清空错误日志文件
    with open("error.log", "w", encoding="utf-8") as log:
        log.write("搜狗词库转换错误日志\n" + "="*50 + "\n")

    # 递归获取scel目录下所有的scel文件
    scel_files = []
    for root, dirs, files in os.walk("./scel"):
        for file in files:
            if file.endswith('.scel'):
                scel_files.append(os.path.join(root, file))

    if not scel_files:
        error_msg = "错误：在 ./scel 目录下未找到任何 .scel 文件"
        print(error_msg)
        with open("error.log", "a", encoding="utf-8") as log:
            log.write(error_msg + "\n")
        sys.exit(1)

    dict_file = "luna_pinyin.sogou.dict.yaml"
    dict_file_content = []
    dict_file_header = """# Rime dictionary
# encoding: utf-8
#
# Sogou Pinyin Dict - 搜狗细胞词库
#   
#   https://pinyin.sogou.com/dict/
#
# 包括: 
#
%s
#

---
name: luna_pinyin.sogou
version: "1.0"
sort: by_weight
use_preset_vocabulary: true
...
    """
    sougo_dict_name_list = list(
        map(lambda x: "# * %s" % os.path.splitext(os.path.basename(x))[0], scel_files))
    dict_file_content.append(dict_file_header % "\n".join(sougo_dict_name_list))

    if not os.path.exists("./out"):
        os.mkdir("./out")
    
    for scel_file in scel_files:
        try:
            if not os.path.exists(scel_file):
                error_msg = f"错误：文件不存在: {scel_file}"
                print(error_msg)
                with open("error.log", "a", encoding="utf-8") as log:
                    log.write(error_msg + "\n")
                continue
                
            if os.path.getsize(scel_file) < 0x2628:  # 最小有效文件大小
                error_msg = f"错误：文件太小，可能不是有效的搜狗词库文件: {scel_file}"
                print(error_msg)
                with open("error.log", "a", encoding="utf-8") as log:
                    log.write(error_msg + "\n")
                continue
                
            # 保持原有目录结构
            rel_path = os.path.relpath(scel_file, "./scel")
            out_dir = os.path.join("./out", os.path.dirname(rel_path))
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)

            try:
                records = get_words_from_sogou_cell_dict(scel_file)
                print(f"处理文件: {scel_file}")
                print(f"获取到 {len(records)} 个词条")
                
                out_file = os.path.join("./out", rel_path.replace(".scel", ".txt"))
                with open(out_file, "w") as fout:
                    dict_file_content.extend(save(records, fout))
                print(f"已保存到: {out_file}")
                print("-"*80)
                
            except UnicodeDecodeError as e:
                error_msg = f"错误：文件编码错误 {scel_file}\n详细信息: {str(e)}"
                print(error_msg)
                with open("error.log", "a", encoding="utf-8") as log:
                    log.write(error_msg + "\n")
                continue
            except struct.error as e:
                error_msg = f"错误：文件格式错误 {scel_file}\n详细信息: {str(e)}"
                print(error_msg)
                with open("error.log", "a", encoding="utf-8") as log:
                    log.write(error_msg + "\n")
                continue
            except Exception as e:
                error_msg = f"错误：处理文件时发生未知错误 {scel_file}\n详细信息: {str(e)}"
                print(error_msg)
                with open("error.log", "a", encoding="utf-8") as log:
                    log.write(error_msg + "\n")
                continue
                
        except Exception as e:
            print(f"错误：处理文件时发生错误 {scel_file}")
            print(f"详细信息: {str(e)}")
            continue

    try:
        out_dict_file = os.path.join("./out", dict_file)
        print(f"正在生成合并词典: {out_dict_file}")
        print(f"合并后总词条数: {len(dict_file_content) - 1}")
        with open(out_dict_file, "w") as dictfout:
            dictfout.write("\n".join(dict_file_content))
        print(f"词典已保存到: {out_dict_file}")
    except Exception as e:
        print(f"错误：保存合并词典时发生错误: {out_dict_file}")
        print(f"详细信息: {str(e)}")


if __name__ == "__main__":
    main()
