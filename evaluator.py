import pandas as pd


class ScheduleEvaluator:
    def __init__(self, loader):
        self.loader = loader

        self.base_score = 10000
        self.penalty_missing_lesson = 200
        self.penalty_student_window = 10
        self.penalty_teacher_overload = 50

        self.penalty_group_conflict = 5000
        self.penalty_teacher_conflict = 5000
        self.penalty_room_conflict = 5000
        self.penalty_duplicate_row = 3000
        self.penalty_task_overflow = 3000

        self._slot_day = {int(sid): det["day"] for sid, det in loader.slot_details.items()}
        self._slot_num = {int(sid): int(det["number"]) for sid, det in loader.slot_details.items()}
        self._teacher_max = {
            int(tid): int(info["max_lessons_per_day"])
            for tid, info in loader.teacher_map.items()
        }
        self._required_task_counts = self._build_required_task_counts()
        self._total_required_lessons = int(sum(self._required_task_counts.values()))

    def evaluate(self, schedule_df):
        if schedule_df is None or schedule_df.empty:
            return {
                "score": -10000,
                "errors": ["Расписание пустое"],
                "total_lessons": 0,
                "missing_lessons": self._total_required_lessons,
                "student_windows": 0,
                "teacher_overload": 0,
                "group_conflicts": 0,
                "teacher_conflicts": 0,
                "room_conflicts": 0,
                "duplicate_rows": 0,
                "task_overflow": 0,
            }

        df = schedule_df.copy()
        self._normalize_schedule_types(df)

        total_required = self._total_required_lessons
        actual_count = len(df)
        missing_count = max(0, total_required - actual_count)

        metrics = {
            "total_lessons": actual_count,
            "missing_lessons": missing_count,
            "student_windows": 0,
            "teacher_overload": 0,
            "group_conflicts": 0,
            "teacher_conflicts": 0,
            "room_conflicts": 0,
            "duplicate_rows": 0,
            "task_overflow": 0,
            "score": self.base_score,
            "errors": [],
        }

        metrics["group_conflicts"] = self._count_group_conflicts(df)
        metrics["teacher_conflicts"] = self._count_teacher_conflicts(df)
        metrics["room_conflicts"] = self._count_room_conflicts(df)
        metrics["duplicate_rows"] = self._count_duplicate_rows(df)
        metrics["task_overflow"] = self._count_task_overflow(df)

        metrics["score"] -= metrics["group_conflicts"] * self.penalty_group_conflict
        metrics["score"] -= metrics["teacher_conflicts"] * self.penalty_teacher_conflict
        metrics["score"] -= metrics["room_conflicts"] * self.penalty_room_conflict
        metrics["score"] -= metrics["duplicate_rows"] * self.penalty_duplicate_row
        metrics["score"] -= metrics["task_overflow"] * self.penalty_task_overflow

        metrics["score"] -= metrics["missing_lessons"] * self.penalty_missing_lesson

        metrics["student_windows"] = self._count_group_windows(df)
        metrics["teacher_overload"] = self._check_teacher_load(df)

        metrics["score"] -= metrics["student_windows"] * self.penalty_student_window
        metrics["score"] -= metrics["teacher_overload"] * self.penalty_teacher_overload

        if metrics["group_conflicts"] > 0:
            metrics["errors"].append(f"Конфликты у групп: {metrics['group_conflicts']}")
        if metrics["teacher_conflicts"] > 0:
            metrics["errors"].append(f"Конфликты у преподавателей: {metrics['teacher_conflicts']}")
        if metrics["room_conflicts"] > 0:
            metrics["errors"].append(f"Конфликты у аудиторий: {metrics['room_conflicts']}")
        if metrics["duplicate_rows"] > 0:
            metrics["errors"].append(f"Полные дубли строк: {metrics['duplicate_rows']}")
        if metrics["task_overflow"] > 0:
            metrics["errors"].append(f"Лишние пары сверх плана: {metrics['task_overflow']}")
        if metrics["missing_lessons"] > 0:
            metrics["errors"].append(f"Пропущенные пары: {metrics['missing_lessons']}")

        return metrics

    def _normalize_schedule_types(self, df):
        for col in ["slot_id", "group_id", "subject_id", "teacher_id", "room_id"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        if "lesson_type" in df.columns:
            df["lesson_type"] = df["lesson_type"].astype(str).str.strip().str.lower()

        # не назначено ли одной группе несколько разных пар в один и тот же временной слот

    def _count_group_conflicts(self, df):
        conflicts = df.groupby(["slot_id", "group_id"]).size()
        return int((conflicts[conflicts > 1] - 1).sum()) if not conflicts.empty else 0

        # преподаватель должен вести разные предметы или разные типы занятий в одно и то же время

    def _count_teacher_conflicts(self, df):
        grouped = (
            df.groupby(["slot_id", "teacher_id"])[["subject_id", "lesson_type"]]
            .nunique()
            .reset_index()
        )
        if grouped.empty:
            return 0

        bad = grouped[(grouped["subject_id"] > 1) | (grouped["lesson_type"] > 1)]
        return len(bad)
        # в одной аудитории в один момент времени находится только один преподаватель и ведется один предмет

    def _count_room_conflicts(self, df):
        grouped = (
            df.groupby(["slot_id", "room_id"])[["subject_id", "lesson_type", "teacher_id"]]
            .nunique()
            .reset_index()
        )
        if grouped.empty:
            return 0

        bad = grouped[
            (grouped["subject_id"] > 1)
            | (grouped["lesson_type"] > 1)
            | (grouped["teacher_id"] > 1)
            ]
        return len(bad)

    def _count_duplicate_rows(self, df):
        dedup_cols = ["slot_id", "group_id", "subject_id", "teacher_id", "room_id", "lesson_type"]
        existing_cols = [c for c in dedup_cols if c in df.columns]
        if not existing_cols:
            return 0
        return int(df.duplicated(subset=existing_cols).sum())

        # Сравнивает текущее расписание с учебным планом

    def _count_task_overflow(self, df):
        if not self._required_task_counts:
            return 0

        actual = (
            df.groupby(["group_id", "subject_id", "lesson_type"])  # одна строка = одна пара для группы
            .size()
            .to_dict()
        )

        overflow = 0
        for key, actual_count in actual.items():
            required_count = self._required_task_counts.get(key, 0)
            if actual_count > required_count:
                overflow += actual_count - required_count
        return int(overflow)

    def _build_required_task_counts(self):
        counts = {}
        group_ids = [int(g) for g in self.loader.groups["group_id"].tolist()]

        for _, sub in self.loader.subjects.iterrows():
            subject_id = int(sub["subject_id"])
            lecture_count = int(sub.get("lecture", 0))
            seminar_count = int(sub.get("seminar", 0))
            lab_count = int(sub.get("lab", 0))

            for group_id in group_ids:
                counts[(group_id, subject_id, "lecture")] = lecture_count
                counts[(group_id, subject_id, "seminar")] = seminar_count
                counts[(group_id, subject_id, "lab")] = lab_count

        return counts

    def _count_group_windows(self, df):
        if df.empty:
            return 0

        tmp = pd.DataFrame({
            "group_id": df["group_id"].to_numpy(),
            "day": df["slot_id"].map(self._slot_day).to_numpy(),
            "num": df["slot_id"].map(self._slot_num).to_numpy(),
        }).dropna().drop_duplicates()

        if tmp.empty:
            return 0

        tmp = tmp.sort_values(["group_id", "day", "num"])
        diffs = tmp.groupby(["group_id", "day"])["num"].diff()
        gaps = diffs[diffs > 1] - 1
        return int(gaps.sum())

        # количество уникальных слотов, занятых преподавателем в день

    def _check_teacher_load(self, df):
        if df.empty:
            return 0

        tmp = pd.DataFrame({
            "teacher_id": df["teacher_id"].to_numpy(),
            "day": df["slot_id"].map(self._slot_day).to_numpy(),
            "slot_id": df["slot_id"].to_numpy(),
        }).dropna(subset=["day"])

        if tmp.empty:
            return 0

        counts = (
            tmp.groupby(["teacher_id", "day"])["slot_id"]
            .nunique()
            .reset_index(name="count")
        )
        counts["max"] = counts["teacher_id"].map(self._teacher_max)
        counts = counts.dropna(subset=["max"])
        overloads = (counts["count"] - counts["max"].astype(int)).clip(lower=0).sum()
        return int(overloads)

    def print_report(self, metrics):
        print("\n" + "=" * 40)
        print("ОТЧЕТ ПО КАЧЕСТВУ РАСПИСАНИЯ")
        print(f"Всего пар в таблице: {metrics['total_lessons']}")
        print(
            f"ПРОПУЩЕНО пар: {metrics['missing_lessons']} [X]"
            if metrics["missing_lessons"] > 0
            else "Все пары из плана размещены [OK]"
        )
        print(f"Конфликты у групп: {metrics['group_conflicts']}")
        print(f"Конфликты у преподавателей: {metrics['teacher_conflicts']}")
        print(f"Конфликты у аудиторий: {metrics['room_conflicts']}")
        print(f"Полные дубли строк: {metrics['duplicate_rows']}")
        print(f"Лишние пары сверх плана: {metrics['task_overflow']}")
        print(f"Окна у групп: {metrics['student_windows']}")
        print(f"Перегрузка учителей: {metrics['teacher_overload']}")
        print(f"ИТОГОВЫЙ БАЛЛ: {metrics['score']}")

        if metrics.get("errors"):
            print("Ошибки:")
            for err in metrics["errors"]:
                print(f" - {err}")

        print("=" * 40)
