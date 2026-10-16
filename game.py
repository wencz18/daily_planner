# -*- coding: utf-8 -*-
"""
Daily Planner / 每日计划软件
================================================================
一款用 Python 标准库（tkinter + json）实现的每日计划管理软件。

功能：
  1. 输入计划内容、开始时间、预计时长、优先级；
  2. 自动按开始时间排表，并检测时间冲突（重叠会给出提醒）；
  3. 支持标记完成、删除单条、清空当日计划；
  4. 数据自动保存到同目录 plan_data.json，下次打开自动加载；
  5. 底部统计当日计划总条数、总时长、已完成数量。

依赖：仅 Python 标准库（Python 3.6+ 均可运行，推荐 3.12）。
运行：python game.py   （或在 PyCharm 中直接右键 Run）

作者：二轮面试作业
"""

import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

# ---------------------------------------------------------------- 常量配置
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan_data.json")

PRIORITY_HIGH = "高"
PRIORITY_MID = "中"
PRIORITY_LOW = "低"
PRIORITIES = (PRIORITY_HIGH, PRIORITY_MID, PRIORITY_LOW)

# 优先级 -> 列表中的颜色标记
PRIORITY_MARK = {PRIORITY_HIGH: "!!!", PRIORITY_MID: "!!", PRIORITY_LOW: "!"}

TIME_FMT = "%H:%M"


# ---------------------------------------------------------------- 数据读写
def load_plans(path=DATA_FILE):
    """从 JSON 文件读取计划列表；文件不存在或损坏时返回空列表。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]
    except (json.JSONDecodeError, OSError):
        return []


def save_plans(plans, path=DATA_FILE):
    """把计划列表写入 JSON 文件。"""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(plans, fp, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 核心逻辑
def parse_time(text):
    """把 'HH:MM' 文本解析成分钟数（0~1439）；非法输入返回 None。"""
    text = (text or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        return None
    try:
        moment = datetime.strptime(text, TIME_FMT)
    except ValueError:
        return None
    return moment.hour * 60 + moment.minute


def minutes_to_text(minutes):
    """把分钟数还原成 'HH:MM'。"""
    minutes = int(minutes) % (24 * 60)
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def sort_plans(plans):
    """按开始时间升序排序（时间相同则高优先级在前）。"""
    def key(item):
        start = item.get("start", 0)
        try:
            start = int(start)
        except (TypeError, ValueError):
            start = 0
        order = {PRIORITY_HIGH: 0, PRIORITY_MID: 1, PRIORITY_LOW: 2}
        return (start, order.get(item.get("priority"), 3))

    return sorted(plans, key=key)


def find_conflicts(plans):
    """找出时间上互相重叠的计划，返回冲突描述文本列表。"""
    conflicts = []
    ordered = sort_plans(plans)
    for prev, curr in zip(ordered, ordered[1:]):
        try:
            prev_end = int(prev.get("start", 0)) + int(prev.get("duration", 0))
            curr_start = int(curr.get("start", 0))
        except (TypeError, ValueError):
            continue
        if curr_start < prev_end:
            conflicts.append(
                "%s 与 %s 时间重叠（%s~%s / %s 起）"
                % (
                    prev.get("title", "未命名"),
                    curr.get("title", "未命名"),
                    minutes_to_text(prev.get("start", 0)),
                    minutes_to_text(prev_end),
                    minutes_to_text(curr_start),
                )
            )
    return conflicts


def build_plan(title, time_text, duration_text, priority):
    """校验输入并构造一条计划记录；校验失败时抛出 ValueError。"""
    title = (title or "").strip()
    if not title:
        raise ValueError("计划内容不能为空。")

    start = parse_time(time_text)
    if start is None:
        raise ValueError("开始时间格式应为 HH:MM，例如 09:30。")

    try:
        duration = int(str(duration_text).strip())
    except (TypeError, ValueError):
        raise ValueError("预计时长必须是整数（分钟）。")
    if duration <= 0 or duration > 24 * 60:
        raise ValueError("预计时长应在 1~1440 分钟之间。")

    if priority not in PRIORITIES:
        raise ValueError("优先级只能是 高 / 中 / 低。")

    return {
        "title": title,
        "start": start,
        "duration": duration,
        "priority": priority,
        "done": False,
    }


def summarize(plans):
    """统计条数、总时长、已完成数量。"""
    total = len(plans)
    total_minutes = 0
    done = 0
    for item in plans:
        try:
            total_minutes += int(item.get("duration", 0))
        except (TypeError, ValueError):
            pass
        if item.get("done"):
            done += 1
    return total, total_minutes, done


# ---------------------------------------------------------------- 图形界面
class PlannerApp:
    """每日计划软件的主窗口。"""

    def __init__(self, root):
        self.root = root
        self.plans = load_plans()

        root.title("每日计划软件 - Daily Planner")
        root.geometry("880x600")
        root.minsize(760, 520)

        self._init_style()
        self._build_input_area()
        self._build_table()
        self._build_status_bar()
        self.refresh()

    # ---------------- 界面搭建
    def _init_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=28, font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("Hint.TLabel", font=("Microsoft YaHei UI", 9), foreground="#6B7280")

    def _build_input_area(self):
        header = ttk.Frame(self.root, padding=(16, 14, 16, 6))
        header.pack(fill="x")
        ttk.Label(header, text="每日计划软件", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="输入计划与时间，程序会按时间自动排表，并检测时间冲突。",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        form = ttk.LabelFrame(self.root, text="新增计划", padding=(16, 10, 16, 12))
        form.pack(fill="x", padx=16, pady=(8, 6))

        ttk.Label(form, text="计划内容").grid(row=0, column=0, sticky="w", pady=6)
        self.entry_title = ttk.Entry(form, width=34)
        self.entry_title.grid(row=0, column=1, sticky="we", pady=6, padx=(8, 16))

        ttk.Label(form, text="开始时间").grid(row=0, column=2, sticky="w", pady=6)
        self.entry_time = ttk.Entry(form, width=10)
        self.entry_time.grid(row=0, column=3, sticky="w", pady=6, padx=(8, 16))
        self.entry_time.insert(0, "09:00")

        ttk.Label(form, text="时长(分钟)").grid(row=0, column=4, sticky="w", pady=6)
        self.entry_duration = ttk.Entry(form, width=8)
        self.entry_duration.grid(row=0, column=5, sticky="w", pady=6, padx=(8, 16))
        self.entry_duration.insert(0, "60")

        ttk.Label(form, text="优先级").grid(row=0, column=6, sticky="w", pady=6)
        self.combo_priority = ttk.Combobox(
            form, values=PRIORITIES, width=5, state="readonly"
        )
        self.combo_priority.current(1)
        self.combo_priority.grid(row=0, column=7, sticky="w", pady=6, padx=(8, 0))

        form.columnconfigure(1, weight=1)

        buttons = ttk.Frame(self.root, padding=(16, 0, 16, 8))
        buttons.pack(fill="x")

        ttk.Button(buttons, text="添加计划", command=self.on_add).pack(side="left")
        ttk.Button(buttons, text="标记完成/取消", command=self.on_toggle_done).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="删除选中", command=self.on_delete).pack(side="left")
        ttk.Button(buttons, text="检查冲突", command=self.on_check_conflicts).pack(
            side="left", padx=8
        )
        ttk.Button(buttons, text="清空全部", command=self.on_clear).pack(side="right")

        self.entry_title.bind("<Return>", lambda event: self.on_add())

    def _build_table(self):
        container = ttk.Frame(self.root, padding=(16, 0, 16, 8))
        container.pack(fill="both", expand=True)

        columns = ("time", "duration", "title", "priority", "status")
        self.tree = ttk.Treeview(
            container, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "time": "开始时间",
            "duration": "时长",
            "title": "计划内容",
            "priority": "优先级",
            "status": "状态",
        }
        widths = {"time": 90, "duration": 80, "title": 400, "priority": 70, "status": 90}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "w" if col == "title" else "center"
            self.tree.column(col, width=widths[col], anchor=anchor)

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("done", foreground="#9CA3AF")
        self.tree.tag_configure("high", foreground="#DC2626")
        self.tree.tag_configure("low", foreground="#2563EB")

        self.tree.bind("<Double-1>", lambda event: self.on_toggle_done())

    def _build_status_bar(self):
        self.status_var = tk.StringVar()
        bar = ttk.Label(
            self.root, textvariable=self.status_var, padding=(16, 6), style="Hint.TLabel"
        )
        bar.pack(fill="x")

    # ---------------- 数据刷新
    def refresh(self):
        """按时间重排并刷新表格与统计。"""
        self.plans = sort_plans(self.plans)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, plan in enumerate(self.plans, start=1):
            start = minutes_to_text(plan.get("start", 0))
            end = minutes_to_text(int(plan.get("start", 0)) + int(plan.get("duration", 0)))
            tags = []
            if plan.get("done"):
                tags.append("done")
            elif plan.get("priority") == PRIORITY_HIGH:
                tags.append("high")
            elif plan.get("priority") == PRIORITY_LOW:
                tags.append("low")

            self.tree.insert(
                "",
                "end",
                iid=str(index - 1),
                values=(
                    "%s-%s" % (start, end),
                    "%d 分钟" % int(plan.get("duration", 0)),
                    "%s %s" % (PRIORITY_MARK.get(plan.get("priority"), ""), plan.get("title", "")),
                    plan.get("priority", PRIORITY_MID),
                    "已完成" if plan.get("done") else "未完成",
                ),
                tags=tuple(tags),
            )

        total, minutes, done = summarize(self.plans)
        hours, rest = divmod(minutes, 60)
        self.status_var.set(
            "共 %d 条计划　|　总时长 %d 分钟（%d 小时 %d 分）　|　已完成 %d 条"
            % (total, minutes, hours, rest, done)
        )
        save_plans(self.plans)

    def selected_index(self):
        """返回当前选中行对应的计划下标；未选中返回 None。"""
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    # ---------------- 事件处理
    def on_add(self):
        try:
            plan = build_plan(
                self.entry_title.get(),
                self.entry_time.get(),
                self.entry_duration.get(),
                self.combo_priority.get(),
            )
        except ValueError as error:
            messagebox.showwarning("输入有误", str(error))
            return

        self.plans.append(plan)
        self.entry_title.delete(0, "end")
        self.refresh()

        conflicts = find_conflicts(self.plans)
        if conflicts:
            messagebox.showinfo("时间冲突提醒", "\n".join(conflicts))

    def on_toggle_done(self):
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("提示", "请先在列表中选择一条计划。")
            return
        self.plans[index]["done"] = not self.plans[index].get("done", False)
        self.refresh()

    def on_delete(self):
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("提示", "请先在列表中选择一条计划。")
            return
        title = self.plans[index].get("title", "未命名")
        if messagebox.askyesno("确认删除", "确定要删除「%s」吗？" % title):
            self.plans.pop(index)
            self.refresh()

    def on_check_conflicts(self):
        conflicts = find_conflicts(self.plans)
        if conflicts:
            messagebox.showinfo("时间冲突提醒", "\n".join(conflicts))
        else:
            messagebox.showinfo("时间冲突提醒", "没有检测到时间冲突，安排很合理。")

    def on_clear(self):
        if not self.plans:
            return
        if messagebox.askyesno("确认清空", "确定要清空全部计划吗？该操作不可撤销。"):
            self.plans = []
            self.refresh()


def main():
    root = tk.Tk()
    PlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
