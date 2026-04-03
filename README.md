# Mini NPU Simulator

과제 요구사항에 맞춰 만든 Python 콘솔 프로그램입니다.

구현 범위는 아래를 모두 포함합니다.

- 모드 1: 사용자 3x3 입력 분석
- 모드 2: `data.json` 일괄 분석
- 라벨 정규화(`+`, `cross`, `x` → `Cross`, `X`)
- epsilon 기반 동점 처리(`UNDECIDED`)
- 크기별 성능 분석
- 보너스 1: 2차원 배열 → 1차원 배열(flat) 최적화 비교
- 보너스 2: Cross / X 패턴 자동 생성기

외부 라이브러리는 사용하지 않았고, `json`, `time(perf_counter_ns)`, `argparse`, `pathlib`, `re` 등 표준 라이브러리만 사용했습니다.

---

## 파일 구성

- `main.py`: 메인 실행 파일
- `data.json`: 예시 입력 데이터
- `README.md`: 실행 방법 + 구현 요약 + 결과 리포트

---

## 실행 방법

### 1) 기본 실행(메뉴 선택)

```bash
python main.py
```

실행 후 아래 2개 모드 중 하나를 선택합니다.

1. 사용자 입력 (3x3)
2. data.json 분석

### 2) 바로 3x3 사용자 입력 모드 실행

```bash
python main.py --mode interactive
```

또는

```bash
python main.py --mode 1
```

### 3) 바로 JSON 분석 모드 실행

```bash
python main.py --mode json --data data.json
```

또는

```bash
python main.py --mode 2 --data data.json
```

### 4) 성능 반복 횟수 변경

기본값은 10회입니다.

```bash
python main.py --mode json --data data.json --repeat 1000
```

### 5) 허용오차(epsilon) 변경

```bash
python main.py --mode json --data data.json --epsilon 1e-9
```

### 6) 보너스 패턴 생성기 실행

```bash
python main.py --generate 13
```

위 명령은 13x13 `Cross` / `X` 패턴을 자동 생성해서 콘솔에 출력합니다.

---

## data.json 구조

프로그램은 아래 구조를 기준으로 JSON을 읽습니다.

```json
{
  "filters": {
    "size_5": {
      "cross": [[0, 0, 1, 0, 0], "..."],
      "x": [[1, 0, 0, 0, 1], "..."]
    },
    "size_13": {
      "cross": [[0, 0, 0, "..."], "..."],
      "x": [[1, 0, 0, "..."], "..."]
    },
    "size_25": {
      "cross": [[0, 0, 0, "..."], "..."],
      "x": [[1, 0, 0, "..."], "..."]
    }
  },
  "patterns": {
    "size_5_1": {
      "input": [[1, 0, 0, 0, 1], "..."],
      "expected": "x"
    },
    "size_13_1": {
      "input": [[0.5, 0.0, 0.0, "..."], "..."],
      "expected": "+"
    }
  }
}
```

### 내부 표준 라벨

프로그램 내부에서는 아래 2개 라벨만 사용합니다.

- `Cross`
- `X`

정규화 규칙은 다음과 같습니다.

- `expected` 값: `+` → `Cross`, `x` → `X`
- `filter` 키: `cross` → `Cross`, `x` → `X`

즉, PASS/FAIL 비교는 모두 표준 라벨 기준으로 수행합니다.

---

## 구현 요약

### 1. MAC 연산

기본 MAC 연산은 `mac_score()` 함수에서 수행합니다.

- 입력 패턴과 필터를 같은 위치끼리 곱합니다.
- 곱한 결과를 모두 더합니다.
- NumPy 없이 이중 반복문으로 직접 구현했습니다.
- 결과 타입은 `float` 입니다.

### 2. 입력 검증

모드 1에서는 한 줄씩 입력을 받아 다음을 검증합니다.

- 행 개수
- 열 개수
- 숫자 파싱 가능 여부

오류가 발생하면 안내 문구를 출력하고 처음부터 다시 입력받습니다.

### 3. JSON 스키마 검증

모드 2에서는 아래 항목을 검증합니다.

- `filters`, `patterns` 존재 여부
- `size_N` / `size_N_idx` 키 형식
- 필터와 패턴의 정사각 행렬 여부
- 필터/패턴 크기 일치 여부
- `input`, `expected` 필드 존재 여부
- 숫자 데이터 여부

중요한 점은, 개별 케이스가 잘못되어도 프로그램이 비정상 종료되지 않도록 만들었다는 점입니다.
문제가 있는 케이스는 해당 케이스만 `FAIL` 처리하고 다음 케이스 분석을 계속 진행합니다.

### 4. 동점 처리 정책

점수 비교는 epsilon 기반으로 처리합니다.

```python
abs(score_cross - score_x) < 1e-9
```

위 조건을 만족하면 `UNDECIDED`로 판정합니다.

### 5. 보너스 1: 메모리 접근 최적화

기본 구현은 2차원 배열 인덱싱(`matrix[row][col]`)을 사용합니다.
보너스 구현은 `flatten_matrix()`로 1차원 배열로 변환한 뒤 `mac_score_flat()`에서 선형 접근을 수행합니다.

핵심 차이는 다음과 같습니다.

- 기본 버전: 2중 인덱싱
- 최적화 버전: 1중 인덱싱
- 둘 다 연산량 자체는 `O(N^2)`
- 하지만 파이썬 레벨 인덱싱 오버헤드가 줄어드는 효과가 있습니다.

### 6. 보너스 2: 패턴 생성기

`generate_cross_pattern(size)`와 `generate_x_pattern(size)`를 구현했습니다.
이 함수들은 아래 곳에서 재사용됩니다.

- `--generate N` 옵션 출력
- 성능 분석용 입력 생성
- 예시 데이터 생성

즉, 보너스 요구사항인 “생성된 패턴을 모드 1/성능 분석에 재활용” 구조를 코드 레벨에서 반영했습니다.

---

## 예시 실행

### JSON 분석 예시

```bash
python main.py --mode json --data data.json
```

예시 결과 요약:

- 총 테스트: 8개
- 통과: 7개
- 실패: 1개
- 실패 케이스: `size_13_1`

실패 사유는 스키마 오류가 아니라, 동점 처리 규칙 때문에 `UNDECIDED`가 나왔기 때문입니다.

---

## 결과 리포트

이번 예시 `data.json`은 의도적으로 1개의 실패 케이스를 포함하도록 구성했습니다.
`size_13_1`은 `Cross` 패턴과 `X` 패턴을 0.5 : 0.5 비율로 섞은 입력이라서 두 필터의 점수가 동일하게 나옵니다.
이 경우 프로그램은 epsilon 정책에 따라 `UNDECIDED`를 반환합니다.
하지만 `expected`는 `X`로 들어 있으므로 최종 결과는 `FAIL`입니다.
이 실패는 구현 오류가 아니라 비교 정책이 설계대로 동작한 결과입니다.
즉, 이 케이스는 “로직 문제”가 아니라 “판정 규칙에 의해 의도적으로 발생한 실패”라고 해석할 수 있습니다.
반대로 나머지 케이스들이 PASS가 된 이유는 라벨 정규화가 먼저 적용되어 `+`, `cross`, `x`가 내부적으로 `Cross`, `X`로 안정적으로 통일되기 때문입니다.
또한 점수 계산을 정수 전용으로 가정하지 않고 `float`까지 허용했기 때문에, 가중치가 섞인 패턴도 동일한 MAC 로직으로 처리할 수 있습니다.
만약 실제 채점용 `data.json`에서 실패가 발생한다면 원인은 크게 세 가지로 나눠서 볼 수 있습니다.
첫째, JSON 키 형식이나 크기 불일치 같은 데이터/스키마 문제입니다.
둘째, 라벨 정규화 누락처럼 비교 전에 표준 라벨로 변환하지 않은 로직 문제입니다.
셋째, 부동소수점 비교에서 epsilon 없이 단순 `==` 비교를 사용했을 때 생기는 수치 비교 문제입니다.
이 구현은 위 세 가지를 분리해서 보도록 만들었고, 특히 개별 실패 사유를 메시지로 남겨 디버깅이 쉽도록 했습니다.

### 시간 복잡도 분석

MAC 연산은 입력 패턴의 모든 칸을 한 번씩 방문하므로 연산 횟수는 정확히 `N^2` 입니다.
예를 들어 3x3은 9회, 5x5는 25회, 13x13은 169회, 25x25는 625회의 곱셈-누산이 필요합니다.
따라서 이 구현의 점근적 시간 복잡도는 `O(N^2)` 입니다.
최적화 버전 역시 모든 원소를 한 번씩 순회하므로 복잡도는 동일하게 `O(N^2)` 입니다.
다만 2차원 인덱싱을 1차원 선형 인덱싱으로 바꾸면 파이썬 인터프리터가 처리해야 할 인덱스 접근 비용이 줄어들 수 있습니다.
즉, 보너스 최적화는 “빅오를 바꾸는 최적화”가 아니라 “상수 계수를 줄이는 최적화”라고 보는 것이 맞습니다.
실제 측정에서도 크기가 커질수록 절대 시간은 증가했고, 이는 `N^2` 증가와 같은 방향을 보였습니다.

### 예시 성능 측정 (`--repeat 1000`)

아래 값은 현재 실행 환경에서 `python main.py --mode json --data data.json --repeat 1000`으로 측정한 예시입니다.
실행 환경이 바뀌면 숫자는 달라질 수 있지만, 크기가 커질수록 시간이 증가하는 경향과 최적화 버전이 더 빠른 경향은 유지됩니다.

| 크기 | 기본 MAC 평균(ms) | 최적화 MAC 평균(ms) | 개선율 | 연산 횟수 |
|---|---:|---:|---:|---:|
| 3x3 | 0.000573 | 0.000280 | 51.03% | 9 |
| 5x5 | 0.001073 | 0.000654 | 39.08% | 25 |
| 13x13 | 0.005692 | 0.003526 | 38.06% | 169 |
| 25x25 | 0.020286 | 0.015492 | 23.63% | 625 |

이 표를 보면 연산 횟수 `N^2`가 커질수록 평균 시간도 함께 증가합니다.
또한 최적화 버전은 모든 크기에서 기본 버전보다 낮은 시간을 보였고, 이는 flat 배열 접근이 실제로 도움이 되었음을 보여줍니다.
다만 개선율은 입력 크기와 실행 환경에 따라 조금씩 달라질 수 있습니다.

---

## 참고 사항

- 모드 1은 과제 요구에 맞게 3x3 고정 입력을 받습니다.
- 모드 2는 `size_5`, `size_13`, `size_25` 필터를 읽도록 구성했습니다.
- 성능 분석 표에는 과제 예시 흐름에 맞춰 3x3, 5x5, 13x13, 25x25를 함께 출력합니다.
- `data.json`은 예시 파일이므로 실제 채점 데이터가 있다면 같은 형식으로 바꿔 넣으면 됩니다.


### code 평가용
```
#!/usr/bin/env python3
"""Mini NPU Simulator

과제 요구사항에 맞춘 콘솔 애플리케이션입니다.

기능
- 모드 1: 3x3 사용자 입력 분석
- 모드 2: data.json 일괄 분석
- 보너스 1: 2차원 배열 -> 1차원 배열(flat) 최적화 및 성능 비교
- 보너스 2: Cross / X 패턴 자동 생성기

제약
- 외부 라이브러리 사용 금지 (표준 라이브러리만 사용)
- MAC 연산은 반복문으로 직접 구현
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

Matrix = List[List[float]]
FlatMatrix = List[float]

STANDARD_CROSS = "Cross"
STANDARD_X = "X"
UNDECIDED = "UNDECIDED"
EPSILON = 1e-9
DEFAULT_REPEAT = 10
PATTERN_KEY_RE = re.compile(r"^size_(\d+)_(.+)$")
SIZE_KEY_RE = re.compile(r"^size_(\d+)$")


@dataclass
class CaseResult:
    """data.json의 개별 패턴 분석 결과."""

    case_id: str
    size: Optional[int]
    cross_score: Optional[float]
    x_score: Optional[float]
    predicted: Optional[str]
    expected: Optional[str]
    passed: bool
    reason: Optional[str] = None


@dataclass
class BenchmarkResult:
    """크기별 성능 측정 결과."""

    size: int
    basic_ms: float
    optimized_ms: float
    operations: int

    @property
    def improvement_pct(self) -> float:
        if self.basic_ms <= 0:
            return 0.0
        return (1.0 - (self.optimized_ms / self.basic_ms)) * 100.0


def normalize_label(value: Any) -> str:
    """여러 형태의 라벨을 표준 라벨(Cross/X)로 정규화한다."""
    if not isinstance(value, str):
        raise ValueError(f"문자열 라벨이 아닙니다: {value!r}")

    raw = value.strip()
    lowered = raw.lower()

    if lowered in {"cross", "+", "plus"}:
        return STANDARD_CROSS
    if lowered == "x" or raw == "X":
        return STANDARD_X

    raise ValueError(f"지원하지 않는 라벨입니다: {value!r}")


def format_number(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    if abs(value - int(value)) < EPSILON:
        return f"{value:.1f}"
    return f"{value:.12f}".rstrip("0").rstrip(".")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def coerce_matrix(obj: Any, *, context: str, expected_size: Optional[int] = None) -> Matrix:
    """JSON/입력 데이터를 float 행렬로 검증 및 변환한다."""
    if not isinstance(obj, list) or not obj:
        raise ValueError(f"{context}: 2차원 배열(list of lists)이어야 합니다.")

    matrix: Matrix = []
    row_length: Optional[int] = None

    for row_index, row in enumerate(obj, start=1):
        if not isinstance(row, list):
            raise ValueError(f"{context}: {row_index}행이 리스트가 아닙니다.")

        if row_length is None:
            row_length = len(row)
            if row_length == 0:
                raise ValueError(f"{context}: 빈 행은 허용되지 않습니다.")
        elif len(row) != row_length:
            raise ValueError(f"{context}: 행 길이가 서로 다릅니다.")

        converted_row: List[float] = []
        for col_index, value in enumerate(row, start=1):
            if not is_number(value):
                raise ValueError(
                    f"{context}: ({row_index}, {col_index}) 값이 숫자가 아닙니다: {value!r}"
                )
            converted_row.append(float(value))
        matrix.append(converted_row)

    size = len(matrix)
    if row_length != size:
        raise ValueError(f"{context}: 정사각 행렬이 아닙니다. ({size}x{row_length})")

    if expected_size is not None and size != expected_size:
        raise ValueError(
            f"{context}: 기대 크기 {expected_size}x{expected_size}와 실제 크기 {size}x{size}가 다릅니다."
        )

    return matrix


def flatten_matrix(matrix: Matrix) -> FlatMatrix:
    flat: FlatMatrix = []
    for row in matrix:
        for value in row:
            flat.append(value)
    return flat


def mac_score(pattern: Matrix, filter_matrix: Matrix) -> float:
    """2차원 배열 기반 기본 MAC 연산."""
    size = len(pattern)
    total = 0.0
    for row in range(size):
        for col in range(size):
            total += pattern[row][col] * filter_matrix[row][col]
    return total


def mac_score_flat(pattern_flat: FlatMatrix, filter_flat: FlatMatrix) -> float:
    """1차원 배열 기반 최적화 MAC 연산."""
    total = 0.0
    length = len(pattern_flat)
    for index in range(length):
        total += pattern_flat[index] * filter_flat[index]
    return total


def judge_from_scores(score_cross: float, score_x: float, epsilon: float = EPSILON) -> str:
    diff = score_cross - score_x
    if abs(diff) < epsilon:
        return UNDECIDED
    if diff > 0:
        return STANDARD_CROSS
    return STANDARD_X


def judge_ab(score_a: float, score_b: float, epsilon: float = EPSILON) -> str:
    diff = score_a - score_b
    if abs(diff) < epsilon:
        return "판정 불가"
    if diff > 0:
        return "A"
    return "B"


def average_ms(operation: Callable[[], Any], repeat: int) -> float:
    if repeat <= 0:
        raise ValueError("repeat는 1 이상이어야 합니다.")

    start_ns = perf_counter_ns()
    for _ in range(repeat):
        operation()
    elapsed_ns = perf_counter_ns() - start_ns
    return (elapsed_ns / repeat) / 1_000_000.0


def generate_cross_pattern(size: int, on_value: float = 1.0, off_value: float = 0.0) -> Matrix:
    if size <= 0:
        raise ValueError("size는 1 이상이어야 합니다.")

    mid = size // 2
    matrix: Matrix = []
    for row in range(size):
        current_row: List[float] = []
        for col in range(size):
            if row == mid or col == mid:
                current_row.append(on_value)
            else:
                current_row.append(off_value)
        matrix.append(current_row)
    return matrix


def generate_x_pattern(size: int, on_value: float = 1.0, off_value: float = 0.0) -> Matrix:
    if size <= 0:
        raise ValueError("size는 1 이상이어야 합니다.")

    matrix: Matrix = []
    for row in range(size):
        current_row: List[float] = []
        for col in range(size):
            if row == col or row + col == size - 1:
                current_row.append(on_value)
            else:
                current_row.append(off_value)
        matrix.append(current_row)
    return matrix


def blend_matrices(first: Matrix, second: Matrix, first_weight: float, second_weight: float) -> Matrix:
    if len(first) != len(second):
        raise ValueError("블렌드하려는 행렬 크기가 다릅니다.")

    size = len(first)
    blended: Matrix = []
    for row in range(size):
        current_row: List[float] = []
        for col in range(size):
            current_row.append(first[row][col] * first_weight + second[row][col] * second_weight)
        blended.append(current_row)
    return blended


def matrix_to_pretty_lines(matrix: Matrix) -> List[str]:
    lines: List[str] = []
    for row in matrix:
        cells = []
        for value in row:
            if abs(value - int(value)) < EPSILON:
                cells.append(str(int(value)))
            else:
                cells.append(f"{value:.3f}".rstrip("0").rstrip("."))
        lines.append(" ".join(cells))
    return lines


def print_matrix(name: str, matrix: Matrix) -> None:
    print(name)
    for line in matrix_to_pretty_lines(matrix):
        print(line)


def parse_console_row(line: str, size: int) -> List[float]:
    parts = line.strip().split()
    if len(parts) != size:
        raise ValueError(f"입력 형식 오류: 각 줄에 {size}개의 숫자를 공백으로 구분해 입력하세요.")

    row: List[float] = []
    for part in parts:
        try:
            row.append(float(part))
        except ValueError as exc:
            raise ValueError("입력 형식 오류: 숫자만 입력하세요.") from exc
    return row


def read_matrix_from_console(size: int, title: str) -> Matrix:
    print(title)
    while True:
        rows: Matrix = []
        failed = False
        for row_index in range(size):
            prompt = f"{row_index + 1}행> "
            try:
                line = input(prompt)
            except EOFError:
                raise SystemExit("입력이 중단되었습니다.")

            try:
                row = parse_console_row(line, size)
            except ValueError as error:
                print(error)
                print("처음부터 다시 입력해주세요.\n")
                failed = True
                break
            rows.append(row)

        if not failed and len(rows) == size:
            return rows


def print_divider(title: str) -> None:
    print("\n" + "#" * 34)
    print(f"# {title}")
    print("#" * 34)


def benchmark_single_input(pattern: Matrix, filter_matrix: Matrix, repeat: int) -> BenchmarkResult:
    size = len(pattern)
    pattern_flat = flatten_matrix(pattern)
    filter_flat = flatten_matrix(filter_matrix)

    basic_ms = average_ms(lambda: mac_score(pattern, filter_matrix), repeat)
    optimized_ms = average_ms(lambda: mac_score_flat(pattern_flat, filter_flat), repeat)
    return BenchmarkResult(
        size=size,
        basic_ms=basic_ms,
        optimized_ms=optimized_ms,
        operations=size * size,
    )


def benchmark_sizes(sizes: Sequence[int], repeat: int) -> List[BenchmarkResult]:
    results: List[BenchmarkResult] = []
    for size in sizes:
        cross = generate_cross_pattern(size)
        x_pattern = generate_x_pattern(size)
        probe = blend_matrices(cross, x_pattern, 0.7, 0.3)
        results.append(benchmark_single_input(probe, cross, repeat))
    return results


def print_benchmark_table(results: Sequence[BenchmarkResult], repeat: int) -> None:
    print(f"평균/{repeat}회 측정")
    print(f"{'크기':<8}{'기본(ms)':>14}{'최적화(ms)':>16}{'개선율':>12}{'연산 횟수':>12}")
    print("-" * 62)
    for item in results:
        size_text = f"{item.size}x{item.size}"
        print(
            f"{size_text:<8}"
            f"{item.basic_ms:>14.6f}"
            f"{item.optimized_ms:>16.6f}"
            f"{item.improvement_pct:>11.2f}%"
            f"{item.operations:>12}"
        )


def load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 구조는 객체(dict)여야 합니다.")
    return data


def load_filter_sets(filters_obj: Any) -> Tuple[Dict[int, Dict[str, Matrix]], List[str]]:
    errors: List[str] = []
    filter_sets: Dict[int, Dict[str, Matrix]] = {}

    if not isinstance(filters_obj, dict):
        raise ValueError("filters는 객체(dict)여야 합니다.")

    for size_key, raw_group in filters_obj.items():
        match = SIZE_KEY_RE.match(size_key)
        if match is None:
            errors.append(f"filters.{size_key}: 키 형식은 size_N 이어야 합니다.")
            continue

        size = int(match.group(1))
        if not isinstance(raw_group, dict):
            errors.append(f"filters.{size_key}: 값은 객체(dict)여야 합니다.")
            continue

        normalized_group: Dict[str, Matrix] = {}
        for raw_label, raw_matrix in raw_group.items():
            try:
                label = normalize_label(raw_label)
                matrix = coerce_matrix(
                    raw_matrix,
                    context=f"filters.{size_key}.{raw_label}",
                    expected_size=size,
                )
                normalized_group[label] = matrix
            except ValueError as error:
                errors.append(str(error))

        missing = [label for label in (STANDARD_CROSS, STANDARD_X) if label not in normalized_group]
        if missing:
            errors.append(f"filters.{size_key}: 필요한 필터가 없습니다 -> {', '.join(missing)}")
            continue

        filter_sets[size] = normalized_group

    return filter_sets, errors


def sort_case_id(case_id: str) -> Tuple[int, str]:
    match = PATTERN_KEY_RE.match(case_id)
    if match is None:
        return (10**9, case_id)
    return (int(match.group(1)), case_id)


def analyze_case(case_id: str, case_obj: Any, filter_sets: Dict[int, Dict[str, Matrix]]) -> CaseResult:
    match = PATTERN_KEY_RE.match(case_id)
    if match is None:
        return CaseResult(
            case_id=case_id,
            size=None,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=None,
            passed=False,
            reason="패턴 키 형식 오류: size_{N}_{idx} 형식이어야 합니다.",
        )

    size = int(match.group(1))

    if not isinstance(case_obj, dict):
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=None,
            passed=False,
            reason="패턴 항목은 객체(dict)여야 합니다.",
        )

    if "input" not in case_obj or "expected" not in case_obj:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=None,
            passed=False,
            reason="패턴 항목에 input 또는 expected가 없습니다.",
        )

    try:
        pattern = coerce_matrix(case_obj["input"], context=f"patterns.{case_id}.input", expected_size=size)
    except ValueError as error:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=None,
            passed=False,
            reason=str(error),
        )

    try:
        expected_label = normalize_label(case_obj["expected"])
    except ValueError as error:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=None,
            passed=False,
            reason=str(error),
        )

    filter_group = filter_sets.get(size)
    if filter_group is None:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=expected_label,
            passed=False,
            reason=f"size_{size} 필터를 찾을 수 없습니다.",
        )

    cross_filter = filter_group.get(STANDARD_CROSS)
    x_filter = filter_group.get(STANDARD_X)
    if cross_filter is None or x_filter is None:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=expected_label,
            passed=False,
            reason=f"size_{size}의 Cross/X 필터가 완전하지 않습니다.",
        )

    if len(cross_filter) != size or len(x_filter) != size:
        return CaseResult(
            case_id=case_id,
            size=size,
            cross_score=None,
            x_score=None,
            predicted=None,
            expected=expected_label,
            passed=False,
            reason=f"size_{size} 필터와 패턴의 크기가 일치하지 않습니다.",
        )

    cross_score = mac_score(pattern, cross_filter)
    x_score = mac_score(pattern, x_filter)
    predicted = judge_from_scores(cross_score, x_score)
    passed = predicted == expected_label

    reason: Optional[str] = None
    if not passed:
        if predicted == UNDECIDED:
            reason = "동점(UNDECIDED) 처리 규칙에 따라 FAIL"
        else:
            reason = f"예상값({expected_label})과 판정값({predicted})이 다릅니다."

    return CaseResult(
        case_id=case_id,
        size=size,
        cross_score=cross_score,
        x_score=x_score,
        predicted=predicted,
        expected=expected_label,
        passed=passed,
        reason=reason,
    )


def analyze_json_cases(path: Path, repeat: int) -> int:
    print_divider("[1] 필터 로드")

    try:
        data = load_json_file(path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"JSON 로드 실패: {error}")
        return 1

    try:
        filter_sets, filter_errors = load_filter_sets(data.get("filters"))
    except ValueError as error:
        print(f"필터 스키마 오류: {error}")
        return 1

    if filter_sets:
        for size in sorted(filter_sets):
            print(f"✓ size_{size} 필터 로드 완료 ({STANDARD_CROSS}, {STANDARD_X})")
    else:
        print("유효한 필터를 하나도 로드하지 못했습니다.")

    if filter_errors:
        print("\n[필터 경고/오류]")
        for message in filter_errors:
            print(f"- {message}")

    patterns_obj = data.get("patterns")
    if not isinstance(patterns_obj, dict):
        print("patterns는 객체(dict)여야 합니다.")
        return 1

    print_divider("[2] 패턴 분석 (라벨 정규화 적용)")

    results: List[CaseResult] = []
    for case_id in sorted(patterns_obj.keys(), key=sort_case_id):
        result = analyze_case(case_id, patterns_obj[case_id], filter_sets)
        results.append(result)

        print(f"--- {result.case_id} ---")
        if result.cross_score is not None:
            print(f"Cross 점수: {format_number(result.cross_score)}")
        if result.x_score is not None:
            print(f"X 점수: {format_number(result.x_score)}")

        if result.predicted is not None and result.expected is not None:
            status = "PASS" if result.passed else "FAIL"
            print(f"판정: {result.predicted} | expected: {result.expected} | {status}")
        else:
            print("판정: 계산 불가 | FAIL")

        if result.reason:
            print(f"사유: {result.reason}")
        print()

    print_divider("[3] 성능 분석")
    benchmark_results = benchmark_sizes([3, 5, 13, 25], repeat)
    print_benchmark_table(benchmark_results, repeat)

    print_divider("[4] 결과 요약")
    total = len(results)
    passed_count = sum(1 for item in results if item.passed)
    failed_results = [item for item in results if not item.passed]

    print(f"총 테스트: {total}개")
    print(f"통과: {passed_count}개")
    print(f"실패: {len(failed_results)}개")

    if failed_results:
        print("\n실패 케이스:")
        for item in failed_results:
            summary = item.reason or "원인 미상"
            print(f"- {item.case_id}: {summary}")

    return 0


def run_interactive_mode(repeat: int, epsilon: float) -> int:
    print_divider("[1] 필터 입력")
    filter_a = read_matrix_from_console(3, "필터 A (3줄 입력, 공백 구분)")
    print()
    filter_b = read_matrix_from_console(3, "필터 B (3줄 입력, 공백 구분)")

    print("\n저장된 필터")
    print_matrix("A", filter_a)
    print()
    print_matrix("B", filter_b)

    print_divider("[2] 패턴 입력")
    pattern = read_matrix_from_console(3, "패턴 (3줄 입력, 공백 구분)")
    print()
    print_matrix("입력 패턴", pattern)

    score_a = mac_score(pattern, filter_a)
    score_b = mac_score(pattern, filter_b)
    decision = judge_ab(score_a, score_b, epsilon)

    pair_basic_ms = average_ms(lambda: (mac_score(pattern, filter_a), mac_score(pattern, filter_b)), repeat)

    pattern_flat = flatten_matrix(pattern)
    filter_a_flat = flatten_matrix(filter_a)
    filter_b_flat = flatten_matrix(filter_b)
    pair_optimized_ms = average_ms(
        lambda: (mac_score_flat(pattern_flat, filter_a_flat), mac_score_flat(pattern_flat, filter_b_flat)),
        repeat,
    )

    print_divider("[3] MAC 결과")
    print(f"A 점수: {format_number(score_a)}")
    print(f"B 점수: {format_number(score_b)}")
    print(f"연산 시간(기본, 평균/{repeat}회): {pair_basic_ms:.6f} ms")
    print(f"연산 시간(최적화, 평균/{repeat}회): {pair_optimized_ms:.6f} ms")
    if pair_basic_ms > 0:
        improvement_pct = (1.0 - (pair_optimized_ms / pair_basic_ms)) * 100.0
    else:
        improvement_pct = 0.0
    print(f"개선율: {improvement_pct:.2f}%")
    print(f"판정: {decision}")

    print_divider("[4] 성능 분석 (3x3)")
    benchmark = benchmark_single_input(pattern, filter_a, repeat)
    print_benchmark_table([benchmark], repeat)
    return 0


def print_generated_patterns(size: int) -> None:
    cross = generate_cross_pattern(size)
    x_pattern = generate_x_pattern(size)
    print(f"자동 생성 패턴 (크기: {size}x{size})\n")
    print_matrix(f"{STANDARD_CROSS} 패턴", cross)
    print()
    print_matrix(f"{STANDARD_X} 패턴", x_pattern)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mini NPU Simulator")
    parser.add_argument(
        "--mode",
        choices=["interactive", "json", "1", "2"],
        help="interactive(1): 3x3 사용자 입력, json(2): data.json 분석",
    )
    parser.add_argument(
        "--data",
        default="data.json",
        help="JSON 분석 모드에서 사용할 data.json 경로 (기본값: data.json)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=DEFAULT_REPEAT,
        help=f"성능 측정 반복 횟수 (기본값: {DEFAULT_REPEAT})",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=EPSILON,
        help=f"동점 판정 허용오차 (기본값: {EPSILON})",
    )
    parser.add_argument(
        "--generate",
        type=int,
        metavar="N",
        help="보너스: N을 입력하면 NxN Cross/X 패턴을 자동 생성해서 출력",
    )
    return parser


def ask_mode_interactively() -> str:
    print("=== Mini NPU Simulator ===\n")
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")

    while True:
        choice = input("선택: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("1 또는 2를 입력해주세요.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.repeat <= 0:
        print("--repeat 값은 1 이상이어야 합니다.")
        return 1

    if args.epsilon < 0:
        print("--epsilon 값은 0 이상이어야 합니다.")
        return 1

    global EPSILON
    EPSILON = args.epsilon

    if args.generate is not None:
        print_generated_patterns(args.generate)
        return 0

    mode = args.mode or ask_mode_interactively()
    if mode == "1":
        mode = "interactive"
    elif mode == "2":
        mode = "json"

    if mode == "interactive":
        return run_interactive_mode(args.repeat, args.epsilon)

    data_path = Path(args.data)
    return analyze_json_cases(data_path, args.repeat)


if __name__ == "__main__":
    sys.exit(main())

```

data.json
```
{
  "filters": {
    "size_5": {
      "cross": [
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ]
      ],
      "x": [
        [
          1.0,
          0.0,
          0.0,
          0.0,
          1.0
        ],
        [
          0.0,
          1.0,
          0.0,
          1.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          1.0,
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      ]
    },
    "size_13": {
      "cross": [
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      ],
      "x": [
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      ]
    },
    "size_25": {
      "cross": [
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      ],
      "x": [
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      ]
    }
  },
  "patterns": {
    "size_5_1": {
      "input": [
        [
          1.0,
          0.0,
          0.0,
          0.0,
          1.0
        ],
        [
          0.0,
          1.0,
          0.0,
          1.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          1.0,
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      ],
      "expected": "x"
    },
    "size_5_2": {
      "input": [
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ]
      ],
      "expected": "+"
    },
    "size_13_1": {
      "input": [
        [
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5
        ],
        [
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0
        ],
        [
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.5,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.5,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.5,
          0.5,
          0.5,
          0.5,
          0.5,
          0.5,
          1.0,
          0.5,
          0.5,
          0.5,
          0.5,
          0.5,
          0.5
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.5,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.5,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0
        ],
        [
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0
        ],
        [
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.5
        ]
      ],
      "expected": "x"
    },
    "size_13_2": {
      "input": [
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      ],
      "expected": "+"
    },
    "size_13_3": {
      "input": [
        [
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8
        ],
        [
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0
        ],
        [
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.2,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.2,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.2,
          0.2,
          0.2,
          0.2,
          0.2,
          0.2,
          1.0,
          0.2,
          0.2,
          0.2,
          0.2,
          0.2,
          0.2
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.2,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.2,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0,
          0.0
        ],
        [
          0.0,
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8,
          0.0
        ],
        [
          0.8,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.2,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.8
        ]
      ],
      "expected": "x"
    },
    "size_25_1": {
      "input": [
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0,
          1.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ]
      ],
      "expected": "+"
    },
    "size_25_2": {
      "input": [
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0,
          0.0
        ],
        [
          0.0,
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0,
          0.0
        ],
        [
          1.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          1.0
        ]
      ],
      "expected": "x"
    },
    "size_25_3": {
      "input": [
        [
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3
        ],
        [
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0
        ],
        [
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.7,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.7,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          1.0,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7,
          0.7
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.7,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.7,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0
        ],
        [
          0.0,
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0,
          0.0
        ],
        [
          0.0,
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3,
          0.0
        ],
        [
          0.3,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.7,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.3
        ]
      ],
      "expected": "+"
    }
  }
}
```