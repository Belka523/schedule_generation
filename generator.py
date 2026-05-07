import pandas as pd
import random
from collections import defaultdict


class GreedyGenerator:
    def __init__(self, loader):
        self.loader = loader

    def generate(self):
        schedule = []
        teachers = set()
        groups = set()
        rooms = set()
        teacher_load = defaultdict(lambda: defaultdict(int))

        tasks = self._build_task_queue()
        test = []
        #размещение задач
        for task in tasks:
            placed = self._try_place(task, schedule, teachers, groups, rooms, teacher_load)
            if not placed:
                test.append(task)
        if test:
            print(f"не размещено {len(test)} пар")
            print(*test, sep='\n')
        return pd.DataFrame(schedule)

    def _build_task_queue(self):
        lecture_tasks = []
        other_tasks = []
        for _, sub in self.loader.subjects.iterrows():
            s_id = int(sub['subject_id'])
            # лекции
            for _ in range(int(sub.get('lecture', 0))):
                lecture_tasks.append({'s_id': s_id, 'type': 'lecture', 'is_lecture': True})
            # семинары
            for _, group in self.loader.groups.iterrows():
                g_id = int(group['group_id'])
                for t in ['seminar', 'lab']:
                    for _ in range(int(sub.get(t, 0))):
                        other_tasks.append({'g_id': g_id, 's_id': s_id, 'type': t, 'is_lecture': False})

        random.shuffle(lecture_tasks)
        random.shuffle(other_tasks)
        return lecture_tasks + other_tasks

    def _try_place(self, task, schedule, b_teachers, b_groups, b_rooms, t_load):
        s_id = task['s_id']
        s_info = self.loader.subject_arr.get(s_id)
        s_name = str(s_info['subject_name'])

        # поиск преподавателей
        possible_teachers = []
        for tid, d in self.loader.teacher_arr.items():
            if d['specialization'] == s_name:
                if task['is_lecture']:
                    if d.get('is_lecturer', False):
                        possible_teachers.append(tid)
                else:
                    if d['assigned_groups']:
                        if task['g_id'] in d['assigned_groups']:
                            possible_teachers.append(tid)
                    else:
                        if not d.get('is_lecturer', False):
                            possible_teachers.append(tid)

        if not possible_teachers:
            return False
        # сортировка для минимизации окон
        slots = self.loader.all_slots.copy()
        random.shuffle(slots)

        if not task['is_lecture']:
            group_busy = [sid for (sid, g_id) in b_groups if g_id == task['g_id']]
            slots.sort(key=lambda sid: self._slot_priority(sid, group_busy))

        for slot_id in slots:
            day = self.loader.slot_details[slot_id]['day']
            check_groups = self.loader.groups['group_id'].tolist() if task['is_lecture'] else [task['g_id']]

            # проверка группы
            if any((slot_id, g_id) in b_groups for g_id in check_groups):
                continue

            for t_id in possible_teachers:
                # дневной лимит преподавателей
                if (slot_id, t_id) in b_teachers or t_load[t_id][day] >= self.loader.teacher_arr[t_id][
                    'max_lessons_per_day']:
                    continue

                # посик кабинета
                rooms = self.loader.get_rooms_by_type(task['type'])
                for r_id in rooms:
                    if (slot_id, r_id) in b_rooms:
                        continue
                    for g_id in check_groups:
                        schedule.append({
                            "slot_id": slot_id, "group_id": g_id, "subject_id": s_id,
                            "teacher_id": t_id, "room_id": r_id, "lesson_type": task['type']
                        })
                        b_groups.add((slot_id, g_id))

                    b_teachers.add((slot_id, t_id))
                    b_rooms.add((slot_id, r_id))
                    t_load[t_id][day] += 1
                    return True
        return False

    def _slot_priority(self, slot_id, group_busy_slots):
        if not group_busy_slots:
            return 2

        target = self.loader.slot_details[slot_id]
        for b_id in group_busy_slots:
            b = self.loader.slot_details[b_id]
            if target['day'] == b['day'] and abs(target['slot_number'] - b['slot_number']) == 1:
                return 0
        return 1
