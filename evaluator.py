import pandas as pd
from collections import defaultdict


class ScheduleEvaluator:
    def __init__(self, loader):
        self.loader = loader

    def evaluate(self, schedule_df):
        if schedule_df is None or schedule_df.empty:
            return {"score": -10000}

        counts = {
            "group_conflicts": 0,
            "teacher_conflicts": 0,
            "room_conflicts": 0,
            "student_windows": 0,
            "missing_lessons": 0,
            "score": 1000
        }
        records = schedule_df.to_dict('records')

        group_slots = defaultdict(int)
        teacher_lessons = defaultdict(set)
        room_lessons = defaultdict(set)

        group_window = defaultdict(lambda: defaultdict(list))
        skip_tasks = defaultdict(int)

        for row in records:
            slot_id = row['slot_id']
            g_id = row['group_id']
            t_id = row['teacher_id']
            r_id = row['room_id']
            s_id = row['subject_id']
            l_type = row['lesson_type']

            # счетчики конфликтов
            group_slots[(slot_id, g_id)] += 1
            teacher_lessons[(slot_id, t_id)].add((s_id, l_type))
            room_lessons[(slot_id, r_id)].add((t_id, s_id, l_type))

            day = self.loader.slot_details[slot_id]['day']
            slot_num = self.loader.slot_details[slot_id]['slot_number']
            group_window[g_id][day].append(slot_num)

            # счет размещенных пар
            is_lecture = row.get('lesson_type') == 'lecture'
            if is_lecture:
                skip_tasks[(row['subject_id'], 'lecture')] = 1
            else:
                skip_tasks[(g_id, row['subject_id'], row['lesson_type'])] += 1

        # подсчет конфликтов
        for count in group_slots.values():
            if count > 1: counts["group_conflicts"] += (count - 1)
        for lessons in teacher_lessons.values():
            if len(lessons) > 1: counts["teacher_conflicts"] += (len(lessons) - 1)
        for lessons in room_lessons.values():
            if len(lessons) > 1: counts["room_conflicts"] += (len(lessons) - 1)

        # счет окон
        for g_id, days in group_window.items():
            for day, slots in days.items():
                if len(slots) > 1:
                    slots.sort()
                    for i in range(len(slots) - 1):
                        diff = slots[i + 1] - slots[i]
                        if diff > 1:
                            counts["student_windows"] += (diff - 1)

        # штрафы
        counts["score"] -= (counts["group_conflicts"] * 100)
        counts["score"] -= (counts["teacher_conflicts"] * 100)
        counts["score"] -= (counts["room_conflicts"] * 100)
        counts["score"] -= (counts["student_windows"] * 10)
        return counts

    def print_report(self, metrics):
        print(f"Счет: {metrics['score']}")
        print(f"Конфликты групп: {metrics['group_conflicts']}")
        print(f"Конфликты учителей: {metrics['teacher_conflicts']}")
        print(f"Конфликты аудиторий: {metrics['room_conflicts']}")
        print(f"Окна: {metrics['student_windows']}")
