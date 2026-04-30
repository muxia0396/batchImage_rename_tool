"""
批量图片文件重命名工具 v3.2
- 重新命名模式下强制自动编号，防止重名覆盖
- 保留原文件名模式下编号可选
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sv_ttk

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DRAG_DROP_SUPPORT = True
except ImportError:
    DRAG_DROP_SUPPORT = False

class BatchRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批量图片重命名工具_by_muxia0396")
        self.root.geometry("1100x700")
        self.root.minsize(900, 500)

        self.files = []
        self.history = []
        self.renamed = {}

        self.use_prefix = tk.BooleanVar(value=True)
        self.use_numbering = tk.BooleanVar(value=True)
        self.rename_mode = tk.StringVar(value="保留原文件名")
        self._prev_use_numbering = True   # 记录切换前的编号状态

        self.fix_combobox_blue()
        self.setup_ui()

        # 必须放在 UI 构建之后，因为需要引用 self.numbering_check
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        if DRAG_DROP_SUPPORT:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)

    def fix_combobox_blue(self):
        style = ttk.Style()
        current = sv_ttk.get_theme()
        bg = '#2b2b2b' if current == 'dark' else '#f0f0f0'
        fg = 'white' if current == 'dark' else 'black'
        style.configure('TCombobox', fieldbackground=bg)
        style.map('TCombobox',
                  fieldbackground=[('readonly', bg), ('disabled', bg)],
                  selectbackground=[('readonly', bg), ('focus', bg), ('!focus', bg)],
                  selectforeground=[('readonly', fg), ('focus', fg)])

    # ---------- 界面布局 ----------
    def setup_ui(self):
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="📁 选择文件夹", command=self.select_folder).pack(side="left", padx=2)
        ttk.Button(toolbar, text="➕ 添加文件", command=self.add_files).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10, pady=2)

        # 模式
        mode_frame = ttk.Frame(toolbar)
        mode_frame.pack(side="left", padx=(0, 2))
        ttk.Label(mode_frame, text="模式：").pack(side="left")
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.rename_mode,
            values=["保留原文件名", "重新命名"],
            state="readonly",
            width=14
        )
        self.mode_combo.pack(side="left")

        # 前缀
        prefix_frame = ttk.Frame(toolbar)
        prefix_frame.pack(side="left", padx=2)
        ttk.Checkbutton(prefix_frame, text="添加前缀", variable=self.use_prefix,
                        command=self.on_setting_change).pack(side="left")
        self.prefix_var = tk.StringVar()
        self.prefix_entry = ttk.Entry(prefix_frame, textvariable=self.prefix_var, width=12)
        self.prefix_entry.pack(side="left", padx=2)
        self.prefix_var.trace_add("write", lambda *a: self.preview_rename())

        # 编号（复选框需要保存引用）
        number_frame = ttk.Frame(toolbar)
        number_frame.pack(side="left", padx=(15, 2))
        self.numbering_check = ttk.Checkbutton(number_frame, text="自动编号", variable=self.use_numbering,
                                              command=self.on_setting_change)
        self.numbering_check.pack(side="left")
        ttk.Label(number_frame, text="起始：").pack(side="left")
        self.start_num_var = tk.IntVar(value=1)
        spinbox = ttk.Spinbox(number_frame, from_=0, to=9999,
                              textvariable=self.start_num_var, width=5)
        spinbox.pack(side="left", padx=2)
        self.start_num_var.trace_add("write", lambda *a: self.preview_rename())

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10, pady=2)
        self.theme_btn = ttk.Button(toolbar, text="🌙深色/浅色", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=5)

        # 主内容区域
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_pane, padding=5)
        main_pane.add(left_frame, weight=3)

        list_toolbar = ttk.Frame(left_frame)
        list_toolbar.pack(fill="x", pady=(0, 5))
        ttk.Label(list_toolbar, text="文件列表", font=("Segoe UI", 10, "bold")).pack(side="left")

        right_btns = ttk.Frame(list_toolbar)
        right_btns.pack(side="right")
        ttk.Button(right_btns, text="🔄 刷新预览", command=self.refresh_display).pack(side="left", padx=2)
        ttk.Button(right_btns, text="❌ 移除所有文件", command=self.clear_list).pack(side="left", padx=2)

        columns = ("original", "preview")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="tree headings",
                                 selectmode="extended")
        self.tree.heading("#0", text="路径")
        self.tree.heading("original", text="原文件名")
        self.tree.heading("preview", text="预览名称")
        self.tree.column("#0", width=80, minwidth=50)
        self.tree.column("original", width=180, minwidth=100)
        self.tree.column("preview", width=180, minwidth=100)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        right_frame = ttk.Frame(main_pane, padding=10)
        main_pane.add(right_frame, weight=1)

        opts_group = ttk.LabelFrame(right_frame, text="操作选项", padding=10)
        opts_group.pack(fill="x", pady=5)
        self.overwrite_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_group, text="保存时覆盖原图", variable=self.overwrite_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(opts_group, text="保留原始扩展名",
                        variable=tk.BooleanVar(value=True)).pack(anchor="w", pady=2)

        btn_group = ttk.LabelFrame(right_frame, text="执行操作", padding=10)
        btn_group.pack(fill="x", pady=10)

        ttk.Button(btn_group, text="🚀 批量重命名", command=self.batch_rename,
                   style="Accent.TButton").pack(fill="x", pady=3)
        ttk.Button(btn_group, text="↩ 撤销操作", command=self.undo_rename).pack(fill="x", pady=3)
        ttk.Button(btn_group, text="❌ 清空列表", command=self.clear_list).pack(fill="x", pady=3)

        log_frame = ttk.LabelFrame(self.root, text="操作日志", padding=5)
        log_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.log_text = tk.Text(log_frame, height=5, state="normal", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # ---------- 模式切换强制编号 ----------
    def on_mode_change(self, event=None):
        mode = self.rename_mode.get()
        if mode == "重新命名":
            self._prev_use_numbering = self.use_numbering.get()  # 记住当前状态
            self.use_numbering.set(True)                         # 强制开启
            self.numbering_check.configure(state="disabled")     # 禁用复选框
        else:  # 保留原文件名
            self.numbering_check.configure(state="normal")       # 恢复可用
            self.use_numbering.set(self._prev_use_numbering)     # 恢复原状态
        self.preview_rename()

    # ---------- 其余方法保持不变 ----------
    def on_setting_change(self):
        self.preview_rename()

    def _add_paths(self, paths):
        added = 0
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for f in sorted(path.iterdir()):
                    if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"):
                        if f not in self.files:
                            self.files.append(f)
                            added += 1
            elif path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"):
                if path not in self.files:
                    self.files.append(path)
                    added += 1
        self.refresh_tree()
        self.log(f"已添加 {added} 个文件")

    def select_folder(self):
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder:
            self._add_paths([folder])

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择图片文件",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tiff;*.webp")]
        )
        if paths:
            self._add_paths(paths)

    def on_drop(self, event):
        if not DRAG_DROP_SUPPORT:
            return
        raw = event.data
        paths = []
        for item in raw.split():
            item = item.strip('{}')
            if os.path.exists(item):
                paths.append(item)
        self._add_paths(paths)

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for f in self.files:
            node_id = self.tree.insert("", "end",
                                       text=f.parent.name if f.parent else "",
                                       values=(f.name, ""))
            self.tree.set(node_id, "original", f.name)
        self.preview_rename()

    def refresh_display(self):
        updated_files = []
        for f in self.files:
            if f.exists():
                updated_files.append(f)
            else:
                self.log(f"警告：文件不再存在 - {f}")
        self.files = updated_files

        items = self.tree.get_children()
        if len(items) != len(self.files):
            self.refresh_tree()
            return

        for i, item_id in enumerate(items):
            f = self.files[i]
            self.tree.set(item_id, "original", f.name)
            self.tree.item(item_id, text=f.parent.name if f.parent else "")
        self.preview_rename()

    def preview_rename(self, *args):
        use_p = self.use_prefix.get()
        use_n = self.use_numbering.get()
        prefix = self.prefix_var.get().strip() if use_p else ""
        start_num = self.start_num_var.get() if use_n else 0
        mode = self.rename_mode.get()

        # 重新命名模式下保险：即使通过其他途径关闭了编号，此处仍强制按编号处理
        if mode == "重新命名" and not use_n:
            use_n = True
            self.use_numbering.set(True)
            self.numbering_check.configure(state="disabled")

        items = self.tree.get_children()
        for i, item_id in enumerate(items):
            original = self.tree.set(item_id, "original")
            if not original:
                continue
            stem = Path(original).stem
            ext = Path(original).suffix

            if mode == "重新命名":
                parts = []
                if use_p and prefix:
                    parts.append(prefix)
                if use_n:
                    parts.append(str(start_num + i))
                prefix_str = "_".join(parts) if parts else ""
                if not prefix_str:
                    prefix_str = stem
                new_name = f"{prefix_str}{ext}"
            else:
                parts = []
                if use_p and prefix:
                    parts.append(prefix)
                if use_n:
                    parts.append(str(start_num + i))
                prefix_str = "_".join(parts) if parts else ""
                if prefix_str:
                    new_name = f"{prefix_str}_{stem}{ext}"
                else:
                    new_name = original

            self.tree.set(item_id, "preview", new_name)
        self.tree.update_idletasks()

    def batch_rename(self):
        if not self.files:
            messagebox.showwarning("警告", "没有可重命名的文件！")
            return

        items = self.tree.get_children()
        if not items:
            return

        self.history.clear()
        self.renamed.clear()
        success = 0

        for item_id in items:
            original_name = self.tree.set(item_id, "original")
            preview_name = self.tree.set(item_id, "preview")
            if not original_name or not preview_name or original_name == preview_name:
                continue

            target = None
            for f in self.files:
                if f.name == original_name:
                    target = f
                    break
            if target is None:
                continue

            old_path = target
            new_path = target.with_name(preview_name)
            try:
                if self.overwrite_var.get() and new_path.exists():
                    os.remove(new_path)
                os.rename(old_path, new_path)
                self.history.append((old_path, new_path))
                self.renamed[old_path] = new_path
                success += 1
            except Exception as e:
                self.log(f"重命名失败: {original_name} -> {preview_name}，错误: {e}")

        self.files = [self.renamed.get(p, p) for p in self.files]
        self.refresh_tree()
        self.log(f"批量重命名完成！成功: {success} 个文件")
        if success > 0:
            messagebox.showinfo("完成", f"已成功重命名 {success} 个文件！")

    def undo_rename(self):
        if not self.history:
            messagebox.showinfo("提示", "没有可撤销的操作")
            return

        undone = 0
        map_revert = {}
        for old_path, new_path in reversed(self.history):
            try:
                os.rename(new_path, old_path)
                map_revert[new_path] = old_path
                undone += 1
            except Exception as e:
                self.log(f"撤销失败: {new_path} -> {old_path}，错误: {e}")

        self.files = [map_revert.get(p, p) for p in self.files]
        self.history.clear()
        self.renamed.clear()
        self.refresh_tree()
        self.log(f"已撤销 {undone} 个文件")
        if undone > 0:
            messagebox.showinfo("撤销", f"已撤销 {undone} 个文件的重命名")

    def clear_list(self):
        self.files.clear()
        self.refresh_tree()
        self.log("文件列表已清空")

    def toggle_theme(self):
        current = sv_ttk.get_theme()
        sv_ttk.set_theme("light" if current == "dark" else "dark")
        self.fix_combobox_blue()

    def log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")


if __name__ == "__main__":
    if DRAG_DROP_SUPPORT:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
        print("提示：安装 tkinterdnd2 启用拖放：pip install tkinterdnd2")

    sv_ttk.set_theme("light")
    app = BatchRenameApp(root)
    root.mainloop()