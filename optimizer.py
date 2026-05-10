import random
import pandas as pd


class ScheduleOptimizer:
    def __init__(self, loader, evaluator):
        self.loader = loader
        self.evaluator = evaluator
        self._score_cache = {}
        self.required_task_counts = self._build_required_task_counts()

    def _build_required_task_counts(self):
        counts = {}
        group_ids = [int(g) for g in self.loader.groups["group_id"].tolist()]
        for _, sub in self.loader.subjects.iterrows():
            subject_id = int(sub["subject_id"])
            lecture_n = int(sub.get("lecture", 0) or 0)
            seminar_n = int(sub.get("seminar", 0) or 0)
            lab_n = int(sub.get("lab", 0) or 0)

            for group_id in group_ids:
                counts[(group_id, subject_id, "lecture")] = lecture_n
                counts[(group_id, subject_id, "seminar")] = seminar_n
                counts[(group_id, subject_id, "lab")] = lab_n
        return counts

    def optimize(self, initial_df, iterations=250):
        best_df = self._normalize_df(initial_df)
        if best_df.empty:
            print("[!] Оптимизатор: пустое расписание")
            return best_df, self.evaluator.evaluate(best_df)

        # ВАЖНО:
        # теперь оптимизатор допускает неполное расписание.
        # Он отбрасывает только явные конфликты / лишние пары сверх плана.
        if not self._is_valid_schedule(best_df):
            print("[!] Начальное расписание содержит конфликты или лишние пары, оптимизация пропущена")
            return best_df, self.evaluator.evaluate(best_df)

        best_metrics = self.evaluator.evaluate(best_df)
        print(
            f"Начало оптимизации: "
            f"score={best_metrics['score']}, "
            f"missing={best_metrics.get('missing_lessons', 0)}, "
            f"conflicts={self._hard_conflicts(best_metrics)}"
        )

        for i in range(iterations):
            blocks = self._get_blocks(best_df)
            if not blocks:
                break

            block = random.choice(blocks)
            old_slot = int(block["data"]["slot_id"].iloc[0])

            sample_size = min(12, len(self.loader.all_slots))
            if len(self.loader.all_slots) > sample_size:
                candidate_slots = random.sample(self.loader.all_slots, sample_size)
            else:
                candidate_slots = list(self.loader.all_slots)

            improved = False

            for new_slot in candidate_slots:
                if int(new_slot) == old_slot:
                    continue

                candidate_df = best_df.copy()
                candidate_df.loc[block["indexes"], "slot_id"] = int(new_slot)
                candidate_df = self._normalize_df(candidate_df)

                if not self._is_valid_schedule(candidate_df):
                    continue

                candidate_metrics = self.evaluator.evaluate(candidate_df)

                if self._is_better(candidate_metrics, best_metrics):
                    best_df = candidate_df
                    best_metrics = candidate_metrics
                    improved = True
                    if i % 25 == 0:
                        print(
                            f"Итерация {i}: улучшение -> "
                            f"score={best_metrics['score']}, "
                            f"missing={best_metrics.get('missing_lessons', 0)}, "
                            f"conflicts={self._hard_conflicts(best_metrics)}"
                        )
                    break

            if improved:
                continue

        return best_df, best_metrics

    def _normalize_df(self, df):
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "slot_id", "group_id", "subject_id",
                "teacher_id", "room_id", "lesson_type"
            ])

        normalized = df.copy().reset_index(drop=True)

        required_cols = ["slot_id", "group_id", "subject_id", "teacher_id", "room_id", "lesson_type"]
        for col in required_cols:
            if col not in normalized.columns:
                normalized[col] = None

        for col in ["slot_id", "group_id", "subject_id", "teacher_id", "room_id"]:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce").fillna(0).astype(int)

        normalized["lesson_type"] = normalized["lesson_type"].astype(str).str.strip().str.lower()

        normalized = normalized.drop_duplicates(
            subset=["slot_id", "group_id", "subject_id", "teacher_id", "room_id", "lesson_type"]
        ).reset_index(drop=True)

        return normalized[required_cols]

    def _get_blocks(self, df):
        grouped = df.groupby(
            ["slot_id", "subject_id", "teacher_id", "room_id", "lesson_type"],
            sort=False
        )
        return [{"indexes": block.index.tolist(), "data": block} for _, block in grouped]

    def _hard_conflicts(self, metrics):
        return (
            int(metrics.get("group_conflicts", 0))
            + int(metrics.get("teacher_conflicts", 0))
            + int(metrics.get("room_conflicts", 0))
            + int(metrics.get("duplicate_rows", 0))
            + int(metrics.get("task_overflow", 0))
        )

    def _is_better(self, candidate_metrics, best_metrics):
        # Главный порядок:
        # 1) меньше hard conflicts
        # 2) меньше missing lessons
        # 3) выше score
        candidate_key = (
            self._hard_conflicts(candidate_metrics),
            int(candidate_metrics.get("missing_lessons", 0)),
            -int(candidate_metrics.get("score", -10**9)),
        )
        best_key = (
            self._hard_conflicts(best_metrics),
            int(best_metrics.get("missing_lessons", 0)),
            -int(best_metrics.get("score", -10**9)),
        )
        return candidate_key < best_key

    def _task_counts_not_overflow(self, df):
        current = df.groupby(["group_id", "subject_id", "lesson_type"]).size().to_dict()

        for key, current_count in current.items():
            required = int(self.required_task_counts.get(key, 0))
            if int(current_count) > required:
                return False
        return True

    def _is_valid_schedule(self, df):
        if df is None or df.empty:
            return False

        # Разрешаем неполный план, но не разрешаем overflow
        if not self._task_counts_not_overflow(df):
            return False

        # У группы не может быть 2 занятий в один слот
        if df.duplicated(subset=["slot_id", "group_id"]).any():
            return False

        # У преподавателя в одном слоте допустима только одна сущность занятия
        teacher_nunique = df.groupby(["slot_id", "teacher_id"])[["subject_id", "lesson_type", "room_id"]].nunique()
        if (teacher_nunique > 1).any(axis=1).any():
            return False

        # У аудитории в одном слоте допустима только одна сущность занятия
        room_nunique = df.groupby(["slot_id", "room_id"])[["subject_id", "lesson_type", "teacher_id"]].nunique()
        if (room_nunique > 1).any(axis=1).any():
            return False

        # Полные дубли одной и той же записи запрещены
        lesson_dup = df.duplicated(
            subset=["slot_id", "subject_id", "teacher_id", "room_id", "lesson_type", "group_id"]
        )
        if lesson_dup.any():
            return False

        return True
