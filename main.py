from data_loader import DataLoader
from generator import GreedyGenerator
from evaluator import ScheduleEvaluator
from optimizer import GeneticOptimizer

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
    print(f"сгенерировано занятий: {len(schedule_df)}")
    if unplaced:
        print(f"пропущено: {len(unplaced)}")

    evaluator = ScheduleEvaluator(loader)
    score_before = evaluator.evaluate(schedule_df)
    evaluator.print_report(score_before)
    optimizer = GeneticOptimizer(loader, evaluator, generator, population_size=20, generations=30)
    optimized_df = optimizer.optimize(schedule_df)
    score_after = evaluator.evaluate(optimized_df)
    evaluator.print_report(score_after)
    final_table = optimized_df.copy()


    group_map = loader.groups.set_index('group_id')['group_name'].to_dict()
    final_table['Группа'] = final_table['group_id'].map(group_map)

    final_table['Предмет'] = final_table['subject_id'].apply(
        lambda x: loader.subject_arr.get(x, {}).get('subject_name', x)
    )

    final_table['Преподаватель'] = final_table['teacher_id'].apply(
        lambda x: loader.teacher_arr.get(x, {}).get('full_name', x)
    )

    final_table['Аудитория'] = final_table['room_id'].apply(
        lambda x: loader.room_arr.get(x, {}).get('room_name', x)
    )

    slot_map = loader.slots.set_index('slot_id').to_dict('index')
    final_table['День недели'] = final_table['slot_id'].apply(
        lambda x: slot_map.get(x, {}).get('day', x)
    )
    final_table['Время'] = final_table['slot_id'].apply(
        lambda x: f"{slot_map.get(x, {}).get('start_time', '')} - {slot_map.get(x, {}).get('end_time', '')}"
    )
    final_table['Вид занятия'] = final_table['lesson_type']
    final_table = final_table[
        ['День недели', 'Время', 'Группа', 'Предмет', 'Вид занятия', 'Преподаватель', 'Аудитория']]
    day_order = {'Mon': 1, 'Tue': 2, 'Wed': 3, 'Thu': 4, 'Fri': 5, 'Sat': 6, 'Sun': 7}
    final_table['day_sort'] = final_table['День недели'].map(day_order)

    final_table = final_table.sort_values(by=['day_sort', 'Время', 'Группа'])
    final_table = final_table.drop(columns=['day_sort'])

    output_file = "result_schedule.xlsx"
    final_table.to_excel(output_file, index=False)
    print(f"итоговое расписание сохранено: {output_file}")

