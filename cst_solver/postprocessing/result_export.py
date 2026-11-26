# -*- coding: utf-8 -*-
"""
CST 结果导出 Mixin 模块
========================
封装 ASCIIExport 结果导出功能

@author: PC
"""

import math
import os
import re
import struct
import tempfile

from cst_solver._guards import get_guard_state
from cst_solver.native import execute_vba, _quote


def _temporary_output(path):
    path = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.cst-export-', suffix=os.path.splitext(path)[1], dir=parent)
    os.close(fd)
    os.unlink(temporary)
    return path, temporary


def _validate_complex_field(path):
    """Validate the ASCII export one sample at a time, including its final row."""
    with open(path, encoding='utf-8-sig', errors='replace') as stream:
        labels = re.findall(r'([a-z][a-z0-9]*)\s*\[[^\]]+\]', stream.readline().lower())
        vectors = [[kind + axis + part for axis in 'xyz' for part in ('re', 'im')] for kind in 'eh']
        if labels[:3] != ['x', 'y', 'z'] or labels[3:] not in vectors:
            raise ValueError('Field export lacks labelled complex vector components')
        samples = 0
        for line_number, line in enumerate(stream, start=2):
            line = line.strip()
            if not line or (samples == 0 and not line.strip('- ')):
                continue
            values = [float(column) for column in line.split()]
            if len(values) != 9 or not all(map(math.isfinite, values)):
                raise ValueError(f'Invalid complex field sample on line {line_number}')
            samples += 1
        if not samples:
            raise ValueError('Field export contains no samples')


def _select_vba(tree_path):
    quoted = _quote(tree_path)
    return (f'If Not SelectTreeItem({quoted}) Then Err.Raise 1001, , "Tree selection failed"\n'
            f'If GetSelectedTreeItem() <> {quoted} Then Err.Raise 1002, , "Tree selection mismatch"\n')


class ExportMixin:
    """
    CST 结果导出 Mixin
    提供 1D/2D/3D 结果的 ASCII 导出功能
    """

    def export_complex_field_ascii(self, tree_path, save_path, step=None):
        """Export a selected field and validate its complex Cartesian columns.

        step is a positive fixed spatial width in the project's length unit;
        None leaves the native automatic sampling setting (-1).
        """
        if os.path.splitext(os.fspath(save_path))[1].lower() not in ('.txt', '.asc', '.dat'):
            raise ValueError('Use a .txt, .asc or .dat path for the field export')
        if not isinstance(tree_path, str) or not tree_path.startswith('2D/3D Results\\'):
            raise ValueError('tree_path must be a full 2D/3D Results path')
        if step is not None and (isinstance(step, bool) or not isinstance(step, (int, float)) or not math.isfinite(step) or step <= 0):
            raise ValueError('step must be a positive finite number or None')
        dest, temporary = _temporary_output(save_path)
        try:
            code = ('Sub Main\n' + _select_vba(tree_path) + 'With ASCIIExport\n.Reset\n'
                    + f'.FileName {_quote(temporary)}\n.Mode "FixedWidth"\n'
                    + (f'.Step {step!r}\n' if step is not None else '')
                    + '.Execute\nEnd With\nEnd Sub')
            execute_vba(self.cst_file, code, target='model3d')
            _validate_complex_field(temporary)
            os.replace(temporary, dest)
            get_guard_state(self).mark_result_exported('2d3d')
            return dest
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def capture_model_view_png(self, save_path):
        """Select the model tree and export the current 3D sheet to PNG."""
        if os.path.splitext(os.fspath(save_path))[1].lower() != '.png':
            raise ValueError('save_path must end in .png')
        dest, temporary = _temporary_output(save_path)
        try:
            code = ('Sub Main\n' + _select_vba('Components')
                    + f'Plot.ExportImage {_quote(temporary)}, 0, 0\nEnd Sub')
            execute_vba(self.cst_file, code, target='model3d')
            with open(temporary, 'rb') as stream:
                if stream.read(16) != b'\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR':
                    raise ValueError('CST did not produce a PNG header')
                size = stream.read(8)
                if len(size) != 8 or not all(struct.unpack('>II', size)):
                    raise ValueError('Invalid PNG dimensions')
                stream.seek(-12, os.SEEK_END)
                if stream.read() != b'\x00\x00\x00\x00IEND\xaeB\x60\x82':
                    raise ValueError('Incomplete PNG export')
            os.replace(temporary, dest)
            return dest
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def export_result_1d(self, tree_path, save_path):
        """
        导出 1D 结果到 ASCII 文件

        :param tree_path: str, 导航树路径
        :param save_path: str, 保存路径
        """
        ascii_export = self.cst_file.model3d.ASCIIExport
        self.cst_file.model3d.SelectTreeItem("1D Results\\" + tree_path)
        ascii_export.Reset()
        ascii_export.FileName(save_path)
        ascii_export.Execute()
        get_guard_state(self).mark_result_exported('1d')

    def export_result_2d3d(self, tree_path, save_path, mode='FixedWidth',
                           step=-1,usesubvolume=False,setsubvolume=None):
        """
        导出 2D/3D 结果到 ASCII 文件（**含远场**）

        ⚠️ 守卫层（陷阱 T3）：导出远场/2D-3D 结果后再
        ``save(include_results=True)`` 有把工程写坏的风险，
        守卫会给一条「建议 include_results=False」的警告。

        :param tree_path: str, 导航树路径
        :param save_path: str, 保存路径
        :param mode: str, 'FixedWidth'/'FixedNumber'
        :param step: float/int, 步长/采样数
        """
        ascii_export = self.cst_file.model3d.ASCIIExport
        self.cst_file.model3d.SelectTreeItem(tree_path)
        ascii_export.Reset()
        ascii_export.FileName(save_path)
        ascii_export.Mode(mode)
        if usesubvolume is True:
            xmin,xmax,ymin, ymax,zmin,zmax = setsubvolume
            ascii_export.SetSubvolume(xmin, xmax, ymin, ymax, zmin, zmax)
        if step != -1:
            ascii_export.Step(step)
        ascii_export.Execute()
        get_guard_state(self).mark_result_exported('2d3d')
