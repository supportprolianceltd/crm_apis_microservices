arr = [2, 3, 4, 5, 6]
def two_sum(arr: list[int], target: int)-> list[int]:
    result: dict[int, int] = {}

    for i, num in enumerate(arr):
        print(i, num)
        if target - num in result:
            return [result[target -num], i]
        result[num] = i
    return []

print(two_sum([2, 3, 4, 5, 6,7], 9))