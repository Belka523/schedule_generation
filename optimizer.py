import pandas as pd
import random


class GeneticOptimizer:
    def __init__(self, loader, evaluator, generator, population_size=20, generations=30):
        self.loader = loader
        self.evaluator = evaluator
        self.generator = generator
        self.size = population_size
        self.generations = generations

    def optimize(self, schedule):
        print(f"Популяций: {self.size}, Поколений: {self.generations}")

        population = []
        #расписание от жадного алгоритма
        if schedule is not None and not schedule.empty:
            population.append(schedule.copy())

        print("cоздание начальной популяции")
        while len(population) < self.size:
            res = self.generator.generate()
            if isinstance(res, tuple):
                df = res[0]
            else:
               df = res
            if df is not None and not df.empty:
                population.append(df)

        best_df = None
        best_score = -float('inf')

        for x in range(self.generations):
            # оценка популяции
            evaluated = []
            for ind in population:
                indicators = self.evaluator.evaluate(ind)
                evaluated.append((indicators['score'], ind))

            # сортировка оценки
            evaluated.sort(key=lambda x: x[0], reverse=True)

            current_best_score, current_best_df = evaluated[0]

            # сохранение лучшего расписания
            if current_best_score > best_score:
                best_score = current_best_score
                best_df = current_best_df.copy()
                print(f"поколение {x + 1}: оценка = {best_score}")

            # выбор половины лучших расписаний
            elite_size = max(2, self.size // 2)
            elite = [ind for score, ind in evaluated[:elite_size]]

            new_population = [ind.copy() for ind in elite]

            # скрещивание и мутации
            while len(new_population) < self.size:
                p1 = random.choice(elite)
                p2 = random.choice(elite)

                # Скрещивание двух расписаний по предметам
                new = self._crossover_by_subject(p1, p2)

                if random.random() < 0.4:
                    new = self._mutate_blocks(new)

                new_population.append(new)

            population = new_population

        print(f"итоговая оценка {best_score}")
        return best_df

    def _crossover_by_subject(self, p1, p2):
        #скрещивание
        if p1.empty or p2.empty:
            return p1.copy()

        subjects = p1['subject_id'].unique().tolist()
        random.shuffle(subjects)
        split_point = len(subjects) // 2

        s1_subjects = subjects[:split_point]

        part1 = p1[p1['subject_id'].isin(s1_subjects)]
        part2 = p2[~p2['subject_id'].isin(s1_subjects)]

        res = pd.concat([part1, part2], ignore_index=True)
        return res

    def _mutate_blocks(self, df):
        #мутация
        mutated_df = df.copy()
        if mutated_df.empty:
            return mutated_df

        # группировка по блокам
        grouped = mutated_df.groupby(["slot_id", "subject_id", "teacher_id", "room_id", "lesson_type"], sort=False)
        blocks = [block.index.tolist() for _, block in grouped]

        if not blocks:
            return mutated_df

        num_mutations = max(1, int(len(blocks) * 0.05))

        for _ in range(num_mutations):
            block_indexes = random.choice(blocks)
            new_slot = random.choice(self.loader.all_slots)
            mutated_df.loc[block_indexes, 'slot_id'] = new_slot

        return mutated_df
