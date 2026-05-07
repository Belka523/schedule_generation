import re
import pandas as pd


class DataLoader:
    def __init__(self, file_path="data/test.xlsx"):
        self.file = file_path
        self.teacher_arr = {}
        self.room_arr = {}
        self.subject_arr = {}
        self.room_types = {}
        self.slot_details = {}
        self.all_slots = []
        self.groups = self.teachers = self.subjects = self.rooms = self.slots = None

    def load_all(self):
        try:
            with pd.ExcelFile(self.file) as xls:
                self.groups = pd.read_excel(xls, "Группы")
                self.teachers = pd.read_excel(xls, "Преподаватели")
                self.subjects = pd.read_excel(xls, "Предметы")
                self.rooms = pd.read_excel(xls, "Аудитории")
                self.slots = pd.read_excel(xls, "Слоты")

            self._preprocess()
            print("Данные загружены")
        except Exception as e:
            print(f"Ошибка загрузки: {e}")

    def _preprocess(self):
        # очистка имен колонок и приведение id к int во всех таблицах сразу
        for df in [self.groups, self.teachers, self.subjects, self.rooms, self.slots]:
            df.columns = df.columns.str.strip()
            for col in [c for c in df.columns if "_id" in c.lower() or "slot_number" in c.lower()]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        #приведение строк к нижнему регистру
        if 'subject_name' in self.subjects.columns:
            self.subjects["subject_name"] = self.subjects["subject_name"].astype(str).str.lower().str.strip()
        if 'specialization' in self.teachers.columns:
            self.teachers["specialization"] = self.teachers["specialization"].astype(str).str.lower().str.strip()

        self.subject_arr = self.subjects.set_index("subject_id").to_dict("index")
        self.room_arr = self.rooms.set_index("room_id").to_dict("index")

        # аудитории
        self.room_types = self.rooms.groupby("room_type")["room_id"].apply(list).to_dict()

        # слоты
        self.slot_details = self.slots.set_index("slot_id")[["day", "slot_number"]].to_dict("index")
        self.all_slots = self.slots["slot_id"].tolist()

        #учителя
        self.teacher_arr = {}
        for _, row in self.teachers.iterrows():
            t_id = int(row["teacher_id"])
            self.teacher_arr[t_id] = {
                "full_name": str(row["full_name"]).strip(),
                "specialization": str(row["specialization"]).strip(),
                "max_lessons_per_day": int(row["max_lessons_per_day"]),
                "assigned_groups": self._parse_groups(row.get("id_group", "")),
                "is_lecturer": str(row.get("lecture", "0")).strip() == "1"
            }

    def _parse_groups(self, value):
        if pd.isna(value): return []
        # фикс считывания float вместо txt
        nums = re.findall(r'\d+', str(value))
        return sorted(list(set(int(n) for n in nums if int(n) > 0)))

    def get_rooms_by_type(self, r_type):
        return self.room_types.get(r_type, [])
