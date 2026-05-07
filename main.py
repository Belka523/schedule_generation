from data_loader import DataLoader
from generator import GreedyGenerator
from evaluator import ScheduleEvaluator

loader = DataLoader("data/test.xlsx")
loader.load_all()

generator = GreedyGenerator(loader)
result = generator.generate()
if isinstance(result, tuple):
    schedule_df, unplaced = result
else:
    schedule_df = result
    unplaced = []

if schedule_df is not None and not schedule_df.empty:
    print(f"Сгенерировано занятий: {len(schedule_df)}")
    if unplaced:
        print(f"не размещено: {len(unplaced)}")

    evaluator = ScheduleEvaluator(loader)
    score = evaluator.evaluate(schedule_df)
    evaluator.print_report(score)
    output_file = "result_schedule.xlsx"
    schedule_df.to_excel(output_file, index=False)
    print(f"\n[OK] Итоговое расписание сохранено в: {output_file}")
else:
    print("\n[!] Ошибка при генерации. Расписание пустое.")
