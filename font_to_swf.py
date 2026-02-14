#!/usr/bin/env python3
"""
将TTF/OTF字体转换为Mewgenics游戏的unicodefont.swf格式
直接读取TrueType glyf表，避免RecordingPen的各种问题
"""
import struct
import zlib
import sys
import gc
from fontTools.ttLib import TTFont


class BitWriter:
    """SWF位级写入器"""
    def __init__(self):
        self.buffer = bytearray()
        self.cur = 0
        self.pos = 0

    def write_ub(self, value, n):
        """写入n位无符号整数"""
        for i in range(n - 1, -1, -1):
            self.cur = (self.cur << 1) | ((value >> i) & 1)
            self.pos += 1
            if self.pos == 8:
                self.buffer.append(self.cur)
                self.cur = 0
                self.pos = 0

    def write_sb(self, value, n):
        """写入n位有符号整数（二补码）"""
        if value < 0:
            value = (1 << n) + value
        self.write_ub(value, n)

    def flush(self):
        if self.pos > 0:
            self.buffer.append(self.cur << (8 - self.pos))
            self.cur = 0
            self.pos = 0

    def get_bytes(self):
        self.flush()
        return bytes(self.buffer)


def bits_needed_s(value):
    """有符号整数所需的位数"""
    if value == 0:
        return 1
    if value > 0:
        return value.bit_length() + 1
    return (abs(value) - 1).bit_length() + 1


def _make_empty_shape():
    """生成空字形的shape数据"""
    bw = BitWriter()
    bw.write_ub(0, 4)  # NumFillBits=0
    bw.write_ub(0, 4)  # NumLineBits=0
    bw.write_ub(0, 6)  # EndShape
    return bw.get_bytes()


EMPTY_SHAPE = _make_empty_shape()


def _write_line(bw, dx, dy):
    """写入SWF直线边缘记录"""
    if dx == 0 and dy == 0:
        return
    nb = max(bits_needed_s(dx), bits_needed_s(dy), 2)
    nb = min(nb, 17)  # SWF最大17位
    bw.write_ub(1, 1)  # 边缘
    bw.write_ub(1, 1)  # 直线
    bw.write_ub(nb - 2, 4)
    if dx == 0:
        bw.write_ub(0, 1)  # 非通用
        bw.write_ub(1, 1)  # 垂直
        bw.write_sb(dy, nb)
    elif dy == 0:
        bw.write_ub(0, 1)
        bw.write_ub(0, 1)  # 水平
        bw.write_sb(dx, nb)
    else:
        bw.write_ub(1, 1)  # 通用
        bw.write_sb(dx, nb)
        bw.write_sb(dy, nb)


def _write_curve(bw, cdx, cdy, adx, ady):
    """写入SWF二次贝塞尔曲线边缘记录"""
    nb = max(bits_needed_s(cdx), bits_needed_s(cdy),
             bits_needed_s(adx), bits_needed_s(ady), 2)
    nb = min(nb, 17)
    bw.write_ub(1, 1)  # 边缘
    bw.write_ub(0, 1)  # 曲线
    bw.write_ub(nb - 2, 4)
    bw.write_sb(cdx, nb)
    bw.write_sb(cdy, nb)
    bw.write_sb(adx, nb)
    bw.write_sb(ady, nb)


def encode_tt_glyph(glyf_table, glyph_name, scale):
    """
    直接从glyf表提取TrueType字形并编码为SWF SHAPE。
    TrueType轮廓是二次B样条，直接映射到SWF的二次贝塞尔。
    """
    try:
        glyph = glyf_table[glyph_name]
    except (KeyError, AttributeError):
        return EMPTY_SHAPE

    # 复合字形需要先解析组件
    if glyph.isComposite():
        glyph_table_obj = glyf_table
        # 收集所有组件的坐标
        try:
            coords, flags_arr, end_pts = _decompose_composite(glyf_table, glyph_name)
        except Exception:
            return EMPTY_SHAPE
        if coords is None or len(coords) == 0:
            return EMPTY_SHAPE
    else:
        if not hasattr(glyph, 'numberOfContours') or glyph.numberOfContours <= 0:
            return EMPTY_SHAPE
        if not hasattr(glyph, 'coordinates') or len(glyph.coordinates) == 0:
            return EMPTY_SHAPE
        try:
            # GlyphCoordinates直接迭代返回(x,y)元组
            coords = list(glyph.coordinates)
            flags_arr = list(glyph.flags)
            end_pts = list(glyph.endPtsOfContours)
        except (AttributeError, TypeError):
            return EMPTY_SHAPE

    if not coords or not end_pts:
        return EMPTY_SHAPE

    # 解析轮廓并编码为SWF shape
    bw = BitWriter()
    bw.write_ub(1, 4)  # NumFillBits=1
    bw.write_ub(0, 4)  # NumLineBits=0

    first_contour = True
    start_idx = 0

    for contour_end in end_pts:
        try:
            n = contour_end - start_idx + 1
            if n < 2 or contour_end >= len(coords):
                start_idx = contour_end + 1
                continue

            # 提取本轮廓的点和标志
            c_coords = coords[start_idx:min(contour_end + 1, len(coords))]
            c_flags = flags_arr[start_idx:min(contour_end + 1, len(flags_arr))]
            start_idx = contour_end + 1

            # 生成SWF边缘列表：(type, data...)
            edges = _tt_contour_to_edges(c_coords, c_flags, scale)
            if not edges:
                continue
        except (IndexError, ValueError, TypeError):
            start_idx = contour_end + 1
            continue

        # 轮廓起始点
        sx, sy = edges[0]  # 第一个是起始坐标

        # StyleChange: MoveTo
        bw.write_ub(0, 1)  # 非边缘
        if first_contour:
            bw.write_ub(0, 1)  # StateNewStyles=0
            bw.write_ub(0, 1)  # StateLineStyle=0
            bw.write_ub(0, 1)  # StateFillStyle1=0
            bw.write_ub(1, 1)  # StateFillStyle0=1
            bw.write_ub(1, 1)  # StateMoveTo=1
            mb = max(bits_needed_s(sx), bits_needed_s(sy), 1)
            bw.write_ub(mb, 5)
            bw.write_sb(sx, mb)
            bw.write_sb(sy, mb)
            bw.write_ub(1, 1)  # FillStyle0 = 1
            first_contour = False
        else:
            bw.write_ub(0, 1)
            bw.write_ub(0, 1)
            bw.write_ub(0, 1)
            bw.write_ub(0, 1)
            bw.write_ub(1, 1)  # StateMoveTo=1
            mb = max(bits_needed_s(sx), bits_needed_s(sy), 1)
            bw.write_ub(mb, 5)
            bw.write_sb(sx, mb)
            bw.write_sb(sy, mb)

        cur_x, cur_y = sx, sy

        # 写入边缘
        for edge in edges[1:]:
            if edge[0] == 'L':
                nx, ny = edge[1], edge[2]
                _write_line(bw, nx - cur_x, ny - cur_y)
                cur_x, cur_y = nx, ny
            elif edge[0] == 'Q':
                cx, cy, ax, ay = edge[1], edge[2], edge[3], edge[4]
                _write_curve(bw, cx - cur_x, cy - cur_y, ax - cx, ay - cy)
                cur_x, cur_y = ax, ay

    if first_contour:
        # 没有有效轮廓
        return EMPTY_SHAPE

    # EndShape
    bw.write_ub(0, 6)
    return bw.get_bytes()


def _decompose_composite(glyf_table, glyph_name, depth=0):
    """递归分解复合字形为简单轮廓"""
    if depth > 10:
        return None, None, None

    glyph = glyf_table[glyph_name]
    if not glyph.isComposite():
        if not hasattr(glyph, 'numberOfContours') or glyph.numberOfContours <= 0:
            return None, None, None
        try:
            coords = list(glyph.coordinates)
            flags = list(glyph.flags)
            # 确保ends是整数列表，防止range或其他迭代器对象
            ends = [int(e) for e in glyph.endPtsOfContours]
        except (TypeError, ValueError, AttributeError):
            return None, None, None
        # 坐标是扁平的(x0,y0,x1,y1,...) 还是元组列表? 
        # fontTools glyph.coordinates 是 GlyphCoordinates 对象，支持迭代返回(x,y)元组
        return coords, flags, ends

    all_coords = []
    all_flags = []
    all_ends = []
    offset = 0

    for component in glyph.components:
        comp_name = component.glyphName
        if comp_name not in glyf_table:
            continue
        sub_coords, sub_flags, sub_ends = _decompose_composite(glyf_table, comp_name, depth + 1)
        if sub_coords is None:
            continue

        # 应用变换
        xx, xy, yx, yy, dx, dy = 1, 0, 0, 1, 0, 0
        if hasattr(component, 'transform') and component.transform is not None:
            try:
                t = component.transform
                # transform可能是Transform对象或元组
                if hasattr(t, '__getitem__'):
                    xx, xy, yx, yy = t[0][0], t[0][1], t[1][0], t[1][1]
                elif hasattr(t, 'xx'):
                    # Transform对象属性访问
                    xx, xy, yx, yy = t.xx, t.xy, t.yx, t.yy
            except (TypeError, IndexError, AttributeError):
                pass
        dx = component.x if hasattr(component, 'x') else 0
        dy = component.y if hasattr(component, 'y') else 0

        transformed = []
        for cx, cy in sub_coords:
            nx = round(cx * xx + cy * yx + dx)
            ny = round(cx * xy + cy * yy + dy)
            transformed.append((nx, ny))

        # 确保sub_ends中每个元素都是整数，避免range对象
        shifted_ends = [int(e) + offset for e in sub_ends]
        all_coords.extend(transformed)
        all_flags.extend(sub_flags)
        all_ends.extend(shifted_ends)
        offset += len(transformed)

    if not all_coords:
        return None, None, None
    return all_coords, all_flags, all_ends


def _tt_contour_to_edges(coords, flags, scale):
    """
    将TrueType轮廓（坐标+标志）转换为SWF边缘列表。
    返回: [(sx, sy), ('L', x, y), ('Q', cx, cy, ax, ay), ...]
    
    TrueType规则:
    - flag & 1 = on-curve (线段端点/曲线锚点)
    - flag & 1 = 0 → off-curve (二次贝塞尔控制点)
    - 两个连续off-curve点之间有隐含的on-curve中点
    """
    # 确保coords和flags是列表而不是迭代器
    try:
        coords = list(coords)
        flags = [int(f) for f in flags]
    except (TypeError, ValueError):
        return []
    
    n = len(coords)
    if n < 2:
        return []

    on_curve = [(f & 1) != 0 for f in flags]

    # 找到第一个on-curve点作为起始点
    first_on = -1
    for i in range(n):
        if on_curve[i]:
            first_on = i
            break

    if first_on == -1:
        # 所有点都是off-curve，起始点是第一个和最后一个点的中点
        x0 = round((coords[0][0] + coords[-1][0]) / 2 * scale)
        y0 = round(-(coords[0][1] + coords[-1][1]) / 2 * scale)
        start_x, start_y = x0, y0
        first_on = 0
        all_off = True
    else:
        cx, cy = coords[first_on]
        start_x = round(cx * scale)
        start_y = round(-cy * scale)
        all_off = False

    edges = [(start_x, start_y)]

    # 从first_on+1开始遍历整个轮廓（循环回first_on）
    i = (first_on + 1) % n if not all_off else 0
    cur_x, cur_y = start_x, start_y
    steps = 0

    while steps < n:
        idx = (first_on + 1 + steps) % n if not all_off else steps
        px, py = coords[idx]
        sx = round(px * scale)
        sy = round(-py * scale)

        if on_curve[idx]:
            # on-curve: 直线到此点
            edges.append(('L', sx, sy))
            cur_x, cur_y = sx, sy
            steps += 1
        else:
            # off-curve: 需要找到锚点
            next_idx = (idx + 1) % n
            npx, npy = coords[next_idx]
            nsx = round(npx * scale)
            nsy = round(-npy * scale)

            if on_curve[next_idx]:
                # 下一个是on-curve: 标准二次贝塞尔
                edges.append(('Q', sx, sy, nsx, nsy))
                cur_x, cur_y = nsx, nsy
                steps += 2
            else:
                # 下一个也是off-curve: 隐含中点作为锚点
                mid_x = (sx + nsx) // 2
                mid_y = (sy + nsy) // 2
                edges.append(('Q', sx, sy, mid_x, mid_y))
                cur_x, cur_y = mid_x, mid_y
                steps += 1

    # 闭合轮廓: 回到起始点
    if cur_x != start_x or cur_y != start_y:
        edges.append(('L', start_x, start_y))

    return edges


def build_swf_tag(tag_type, data):
    """构建SWF标签的二进制数据"""
    tag_len = len(data)
    if tag_len < 0x3F:
        header = struct.pack('<H', (tag_type << 6) | tag_len)
        return header + data
    else:
        header = struct.pack('<H', (tag_type << 6) | 0x3F)
        header += struct.pack('<I', tag_len)
        return header + data


def build_swf_rect(xmin, xmax, ymin, ymax):
    """构建SWF RECT结构"""
    vals = [xmin, xmax, ymin, ymax]
    nbits = max(bits_needed_s(v) for v in vals)
    if nbits < 1:
        nbits = 1
    bw = BitWriter()
    bw.write_ub(nbits, 5)
    for v in vals:
        bw.write_sb(v, nbits)
    return bw.get_bytes()


def parse_swf_tags(swf_data):
    """解析SWF文件的所有标签"""
    sig = swf_data[:3].decode('ascii')
    ver = swf_data[3]
    file_len = struct.unpack('<I', swf_data[4:8])[0]

    if sig == 'CWS':
        body = swf_data[:8] + zlib.decompress(swf_data[8:])
    else:
        body = swf_data

    # 跳过RECT
    pos = 8
    nbits = body[pos] >> 3
    total_bits = 5 + nbits * 4
    rect_bytes = (total_bits + 7) // 8
    pos += rect_bytes

    # 帧率和帧数
    frame_rate = struct.unpack('<H', body[pos:pos+2])[0]
    frame_count = struct.unpack('<H', body[pos+2:pos+4])[0]
    pos += 4

    header_end = pos

    tags = []
    while pos < len(body):
        tag_start = pos
        code_and_len = struct.unpack('<H', body[pos:pos+2])[0]
        tag_type = code_and_len >> 6
        tag_len = code_and_len & 0x3F
        pos += 2
        if tag_len == 0x3F:
            tag_len = struct.unpack('<I', body[pos:pos+4])[0]
            pos += 4
        tag_data = body[pos:pos+tag_len]
        tags.append((tag_type, tag_data))
        pos += tag_len
        if tag_type == 0:
            break

    return {
        'version': ver,
        'frame_rate': frame_rate,
        'frame_count': frame_count,
        'header_bytes': body[8:header_end],
        'tags': tags,
    }


def convert_font_to_swf(ttf_path, original_swf_bytes, progress_cb=None):
    """
    将TTF/OTF字体转换为SWF，使用原始unicodefont.swf的骨架结构。
    返回新的SWF字节。
    """
    # 解析原始SWF
    orig = parse_swf_tags(original_swf_bytes)

    # 读取新字体
    font = TTFont(ttf_path)
    units_per_em = font['head'].unitsPerEm
    scale = 20480.0 / units_per_em
    glyf_table = font.get('glyf')
    if glyf_table is None:
        raise ValueError("仅支持TrueType字体(glyf表)，不支持CFF/OpenType")

    # 获取字体度量
    os2 = font.get('OS/2')
    ascent = round((os2.sTypoAscender if os2 else units_per_em * 0.8) * scale)
    descent = round((os2.sTypoDescender if os2 else -units_per_em * 0.2) * scale)
    leading = round((os2.sTypoLineGap if os2 else 0) * scale)

    # 获取字符映射
    cmap = font.getBestCmap()
    if not cmap:
        raise ValueError("字体没有可用的字符映射表")

    # 需要空字形的控制字符（避免游戏中显示为□）
    CTRL_CHARS = {0x09, 0x0A, 0x0D}  # \t \n \r

    # 合并字体码点和控制字符，按Unicode排序
    all_codepoints = sorted(set(cmap.keys()) | CTRL_CHARS)
    total_glyphs = len(all_codepoints)
    if progress_cb:
        progress_cb(f"字体: {ttf_path}")
        progress_cb(f"字形数: {total_glyphs}, unitsPerEm: {units_per_em}")

    # 获取水平度量
    hmtx = font['hmtx']

    # 转换每个字形
    glyph_shapes = []
    code_table = []
    advance_widths = []
    glyph_bounds = []

    for idx, cp in enumerate(all_codepoints):
        try:
            code_table.append(cp)

            # 控制字符：零宽空字形
            if cp in CTRL_CHARS:
                glyph_shapes.append(EMPTY_SHAPE)
                advance_widths.append(0)
                glyph_bounds.append((0, 0, 0, 0))
                continue

            glyph_name = cmap.get(cp)
            if not glyph_name:
                # 字符无映射，使用空字形
                glyph_shapes.append(EMPTY_SHAPE)
                advance_widths.append(0)
                glyph_bounds.append((0, 0, 0, 0))
                continue

            # 获取advance width
            try:
                if glyph_name in hmtx.metrics:
                    aw, lsb = hmtx.metrics[glyph_name]
                else:
                    aw, lsb = units_per_em, 0
                advance_widths.append(round(aw * scale))
            except Exception:
                advance_widths.append(round(units_per_em * scale))
                aw = units_per_em

            # 获取轮廓并编码为SWF shape
            if glyph_name in glyf_table:
                try:
                    shape_bytes = encode_tt_glyph(glyf_table, glyph_name, scale)
                except MemoryError:
                    # 内存不足
                    if progress_cb:
                        progress_cb(f"  [内存不足] 字形 U+{cp:04X} 处理失败，尝试释放内存...")
                    gc.collect()
                    shape_bytes = EMPTY_SHAPE
                except Exception as e:
                    # 单个字形转换失败不中断整个流程
                    if progress_cb:
                        progress_cb(f"  警告: 字形 U+{cp:04X} ({glyph_name}) 转换失败: {str(e)[:50]}")
                    shape_bytes = EMPTY_SHAPE
            else:
                shape_bytes = EMPTY_SHAPE

            glyph_shapes.append(shape_bytes)

            # 字形边界（简化处理）
            glyph_bounds.append((0, round(aw * scale), round(-ascent), round(-descent)))

            if progress_cb and (idx + 1) % 1000 == 0:
                progress_cb(f"  转换字形: {idx+1}/{total_glyphs}")
                # 定期垃圾回收，避免内存累积导致崩溃
                gc.collect()
        except MemoryError:
            # 内存不足是最外层捕获
            if progress_cb:
                progress_cb(f"  [严重] 内存不足！建议：关闭其他程序或使用更小的字体")
            gc.collect()
            glyph_shapes.append(EMPTY_SHAPE)
            advance_widths.append(0)
            glyph_bounds.append((0, 0, 0, 0))
        except Exception as e:
            # 如果单个字形处理完全失败，用空字形代替
            if progress_cb:
                progress_cb(f"  错误: 处理字符 U+{cp:04X} 失败: {str(e)[:50]}")
            glyph_shapes.append(EMPTY_SHAPE)
            advance_widths.append(0)
            glyph_bounds.append((0, 0, 0, 0))

    if progress_cb:
        progress_cb(f"  转换字形: {total_glyphs}/{total_glyphs}")

    num_glyphs = len(code_table)

    # === 构建DefineFont3标签 (tag 75) ===
    df3 = bytearray()
    font_id = 1
    # FontID
    df3 += struct.pack('<H', font_id)
    # Flags: HasLayout=1, WideOffsets=1, WideCodes=1, 其他=0 → 0x8C
    df3.append(0x8C)
    # LanguageCode = 5 (与原始一致)
    df3.append(5)
    # 使用与原始相同的字体名
    orig_font_name = b"Noto Sans CJK TC Regular"
    # 从原始SWF提取字体名
    for tag_type, tag_data in orig['tags']:
        if tag_type == 75 and len(tag_data) > 10:
            name_len = tag_data[4]
            orig_font_name = tag_data[5:5+name_len]
            break
    df3.append(len(orig_font_name))
    df3 += orig_font_name
    # NumGlyphs
    df3 += struct.pack('<H', num_glyphs)

    # OffsetTable (WideOffsets = 4 bytes each)
    # 偏移量相对于OffsetTable的开始位置
    offset_table_size = num_glyphs * 4 + 4  # +4 for CodeTableOffset
    current_offset = offset_table_size
    offsets = []
    for shape in glyph_shapes:
        offsets.append(current_offset)
        current_offset += len(shape)

    for off in offsets:
        df3 += struct.pack('<I', off)
    # CodeTableOffset
    df3 += struct.pack('<I', current_offset)

    # ShapeTable
    for shape in glyph_shapes:
        df3 += shape

    # CodeTable (WideCodes = 2 bytes each)
    for cp in code_table:
        df3 += struct.pack('<H', min(cp, 0xFFFF))

    # Layout data (HasLayout=1)
    # FontAscent, FontDescent, FontLeading（clamp到SI16范围）
    def clamp_s16(v):
        return max(-32768, min(32767, v))
    df3 += struct.pack('<h', clamp_s16(abs(ascent)))
    df3 += struct.pack('<h', clamp_s16(abs(descent)))
    df3 += struct.pack('<h', clamp_s16(abs(leading)))

    # AdvanceTable
    for aw in advance_widths:
        df3 += struct.pack('<h', clamp_s16(aw))

    # BoundsTable (RECT for each glyph)
    for xmin, xmax, ymin, ymax in glyph_bounds:
        df3 += build_swf_rect(xmin, xmax, ymin, ymax)

    # KerningCount = 0
    df3 += struct.pack('<H', 0)

    # === 构建DefineFontAlignZones标签 (tag 73) ===
    align = bytearray()
    align += struct.pack('<H', font_id)
    csm_hint = 1  # thin text
    align.append(csm_hint << 6)
    # 每个字形一个对齐区域
    for i in range(num_glyphs):
        align.append(2)  # NumZoneData = 2
        # Zone data: position, size (以F16.16格式? 不,是f8.8)
        # 简化：写零值
        align += struct.pack('<HH', 0, 0)  # zone0
        align += struct.pack('<HH', 0, 0)  # zone1
        align.append(0x03)  # ZoneMaskY | ZoneMaskX

    # === 组装新SWF ===
    new_tags = bytearray()
    for tag_type, tag_data in orig['tags']:
        if tag_type == 75:
            # 替换DefineFont3
            new_tags += build_swf_tag(75, bytes(df3))
        elif tag_type == 73:
            # 替换DefineFontAlignZones
            new_tags += build_swf_tag(73, bytes(align))
        else:
            # 复制原始标签
            new_tags += build_swf_tag(tag_type, tag_data)

    # 构建SWF文件（header_bytes已包含RECT+帧率+帧数）
    body = bytearray()
    body += orig['header_bytes']
    body += new_tags

    # FWS未压缩格式（与原始SWF一致）
    file_len = 8 + len(body)
    swf = bytearray()
    swf += b'FWS'
    swf.append(orig['version'])
    swf += struct.pack('<I', file_len)
    swf += body

    font.close()
    return bytes(swf)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python font_to_swf.py <input.ttf> <original_swf_bytes_file> [output.swf]")
        sys.exit(1)

    ttf_path = sys.argv[1]
    orig_swf_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "unicodefont_new.swf"

    with open(orig_swf_path, 'rb') as f:
        orig_swf = f.read()

    def progress(msg):
        print(msg)

    result = convert_font_to_swf(ttf_path, orig_swf, progress)
    with open(out_path, 'wb') as f:
        f.write(result)
    print(f"Output: {out_path} ({len(result)} bytes)")
