from data_loader import DataLoader
from generator import GreedyGenerator

loader = DataLoader("data/test.xlsx")
loader.load_all()

generator = GreedyGenerator(loader)
test = generator.generate()

if test is not None and not test.empty:
    print(f"Сгенерировано занятий: {len(test)}")
    final_table = test.copy()

    output_file = "result_schedule.xlsx"
    final_table.to_excel(output_file, index=False)
    print(f"\n[OK] Расписание отсортировано и сохранено в: {output_file}")
else:
    print("\n[!] Ошибка при генерации.")