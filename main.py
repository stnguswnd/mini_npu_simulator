#!/usr/bin/env python3
"""Mini NPU Simulator

과제 요구사항에 맞춘 콘솔 애플리케이션입니다.

이 파일은 "학습용 주석 강화 버전"입니다.
원본 로직은 유지하면서, 각 함수가 왜 필요한지 / 어떤 순서로 동작하는지 /
입력과 출력이 무엇인지를 최대한 자세히 설명했습니다.

핵심 기능
1. 모드 1: 사용자가 콘솔에서 3x3 필터 2개와 3x3 패턴 1개를 직접 입력
2. 모드 2: data.json 안의 여러 패턴을 일괄 분석
3. 보너스 1: 2차원 배열을 1차원 배열로 펴서(flatten) 접근 비용을 줄인 버전 비교
4. 보너스 2: 원하는 크기의 Cross / X 패턴 자동 생성

과제 문서상 요구사항
- MAC(Multiply-Accumulate) 연산을 반복문으로 직접 구현해야 함
- 외부 라이브러리 사용 금지
- JSON 분석 시 라벨 정규화 필요
- epsilon 기반 동점 처리 필요
- 성능 분석 표와 결과 요약 필요
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path #파일 경로를 다루기 위함. 
from time import perf_counter_ns #성능 측정용 함수, ns는 나노초를 의미함. 
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# -----------------------------------------------------------------------------
# 타입 별칭(Type Alias)
# -----------------------------------------------------------------------------
# Matrix: 2차원 행렬. 예) [[0,1,0],[1,1,1],[0,1,0]]
# FlatMatrix: 1차원으로 펼친 행렬. 예) [0,1,0,1,1,1,0,1,0]
Matrix = List[List[float]]
FlatMatrix = List[float]
#함수를 만들 때 input값의 형식을 지정할 때, 보다 직관적으로 쓰기 위함임. 
# def mac_score(pattern: Matrix, filter_matrix: Matrix) -> float:

# -----------------------------------------------------------------------------
# 프로그램 전체에서 공통으로 사용하는 상수들
# -----------------------------------------------------------------------------
STANDARD_CROSS = "Cross"      # 내부 표준 라벨: 십자가 패턴
STANDARD_X = "X"              # 내부 표준 라벨: X 패턴
UNDECIDED = "UNDECIDED"      # 두 점수가 사실상 같을 때 사용하는 판정값
EPSILON = 1e-9                # 부동소수점 비교용 허용 오차 , 차이가 0.00000001로 매우 작을 떄는 같은 것으로 보게끔 함. 
DEFAULT_REPEAT = 10           # 성능 측정 반복 횟수 기본값

# 정규표현식
# size_13_1 같은 패턴 키에서 13, 1 같은 정보를 꺼내기 위해 사용
PATTERN_KEY_RE = re.compile(r"^size_(\d+)_(.+)$")

# size_13 같은 필터 그룹 키를 읽기 위해 사용
SIZE_KEY_RE = re.compile(r"^size_(\d+)$")


# -----------------------------------------------------------------------------
# 결과를 깔끔하게 다루기 위한 데이터 클래스
# -----------------------------------------------------------------------------
@dataclass
class CaseResult:
    """JSON의 개별 패턴 1건을 분석한 결과를 담는 클래스.

    왜 dataclass를 썼나?
    - 딕셔너리보다 필드 의미가 분명하다.
    - 결과를 리스트로 모아 요약하기 쉽다.
    - PASS/FAIL, 점수, 실패 이유를 한 번에 관리하기 좋다.
    """

    case_id: str                    # 예: size_13_1
    size: Optional[int]             # 예: 13
    cross_score: Optional[float]    # Cross 필터와의 MAC 점수
    x_score: Optional[float]        # X 필터와의 MAC 점수
    predicted: Optional[str]        # 프로그램 판정값 (Cross/X/UNDECIDED)
    expected: Optional[str]         # 정답 라벨(정규화 후)
    passed: bool                    # predicted == expected 여부
    reason: Optional[str] = None    # 실패 혹은 경고 사유


@dataclass
class BenchmarkResult:
    """성능 측정 결과 1행을 표현하는 클래스.

    예를 들어 13x13 입력에 대해
    - 기본 2차원 MAC 시간
    - 최적화(flat) MAC 시간
    - 연산 횟수(N^2)
    를 저장한다.
    """

    size: int
    basic_ms: float
    optimized_ms: float
    operations: int

    @property #이 태그는 함수를 호출할 때 ()를 안써도 되게끔 하기 위함
    def improvement_pct(self) -> float:
        """개선율(%) 계산.

        공식:
        1 - (최적화 시간 / 기존 시간)

        예)
        기존 10ms, 최적화 7ms면
        improvement = 30%
        """
        if self.basic_ms <= 0:
            return 0.0
        return (1.0 - (self.optimized_ms / self.basic_ms)) * 100.0


# -----------------------------------------------------------------------------
# 라벨 처리 관련 함수
# -----------------------------------------------------------------------------
def normalize_label(value: Any) -> str:
    """여러 형태의 라벨을 내부 표준 라벨로 통일한다.

    과제 문서에서는 아래 같은 정규화가 필요하다.
    - '+' 또는 'cross' 또는 'plus' -> Cross
    - 'x' 또는 'X'               -> X

    왜 필요한가?
    JSON 작성자는 expected에 '+'를 넣을 수도 있고,
    filter 키에는 'cross'를 넣을 수도 있다.
    프로그램 내부에서는 비교 기준을 하나로 통일해야
    PASS/FAIL 판정을 안정적으로 할 수 있다.
    """
    if not isinstance(value, str):
        raise ValueError(f"문자열 라벨이 아닙니다: {value!r}")

    raw = value.strip()         # 앞뒤 공백 제거
    lowered = raw.lower()       # 대소문자 구분 제거용 소문자 변환

    if lowered in {"cross", "+", "plus"}:
        return STANDARD_CROSS
    if lowered == "x" or raw == "X":
        return STANDARD_X

    raise ValueError(f"지원하지 않는 라벨입니다: {value!r}")


# -----------------------------------------------------------------------------
# 출력 포맷 보조 함수
# -----------------------------------------------------------------------------
def format_number(value: Optional[float]) -> str:
    """숫자를 콘솔에 보기 좋게 출력하기 위한 함수.

    - None 이면 N/A
    - 정수처럼 보이는 값은 소수점 1자리만 표시 (예: 5.0)
    - 그 외에는 불필요한 0을 제거해서 깔끔하게 표시
    """
    if value is None:
        return "N/A"
    if abs(value - int(value)) < EPSILON:
        return f"{value:.1f}" #정수는 소수점 한자리만 출력
    return f"{value:.12f}".rstrip("0").rstrip(".") #소수면 뒤의 불필요한 0과 점을 제거


def is_number(value: Any) -> bool:
    """숫자인지 검사한다.

    bool은 파이썬에서 int의 하위 타입이므로
    True/False가 숫자로 잘못 통과하지 않게 별도 제외한다.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)

#isinstance(값, (int, float)) 이 값이 int거나 float 이냐를 묻는 함수임.
#print(isinstance(3, (int, float)))      # True
#print(isinstance(3.14, (int, float)))   # True
#print(isinstance("hello", (int, float))) # False


# -----------------------------------------------------------------------------
# 행렬 검증 / 변환 함수
# -----------------------------------------------------------------------------
def coerce_matrix(obj: Any, *, context: str, expected_size: Optional[int] = None) -> Matrix:
    """외부 입력(JSON/콘솔 변환 결과)을 '정사각 float 행렬'로 검증한다.

    이 함수가 하는 일
    1. list of lists 형태인지 검사
    2. 빈 행렬인지 검사
    3. 각 행 길이가 같은지 검사
    4. 각 값이 숫자인지 검사
    5. float로 통일
    6. 정사각 행렬인지 검사
    7. expected_size가 있으면 크기 일치 여부 검사

    예를 들어 size_5 패턴인데 실제 input이 5x4이면 FAIL 처리해야 하므로,
    이 함수가 그 검증을 맡는다.
    """

    if not isinstance(obj, list):
        raise ValueError(f"{context}: 최상위 객체는 리스트여야 합니다.")

    if not obj:
        raise ValueError(f"{context}: 빈 행렬은 허용되지 않습니다.")

    matrix: Matrix = []
    row_length: Optional[int] = None

    for row_index, row in enumerate(obj, start=1):
        # 각 행이 리스트여야 한다.
        if not isinstance(row, list):
            raise ValueError(f"{context}: {row_index}행이 리스트가 아닙니다.")

        # 첫 행 길이를 기준 길이로 삼고,
        # 이후 모든 행이 같은 길이인지 검사한다.
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

    # 정사각 행렬인지 검사
    size = len(matrix)
    if row_length != size:
        raise ValueError(f"{context}: 정사각 행렬이 아닙니다. ({size}x{row_length})")

    # 특정 크기를 기대하는 경우(예: size_13이면 13x13이어야 함)
    if expected_size is not None and size != expected_size:
        raise ValueError(
            f"{context}: 기대 크기 {expected_size}x{expected_size}와 실제 크기 {size}x{size}가 다릅니다."
        )

    return matrix


# -----------------------------------------------------------------------------
# flatten / MAC 연산 관련 함수
# -----------------------------------------------------------------------------
def flatten_matrix(matrix: Matrix) -> FlatMatrix:
    """2차원 행렬을 1차원 리스트로 펼친다.

    왜 이게 보너스 최적화인가?
    - 2차원 접근: matrix[row][col]
    - 1차원 접근: flat[index]

    1차원 접근이 인덱싱이 단순해서 일반적으로 조금 더 빠를 수 있다.
    과제의 보너스 과제가 바로 이 아이디어를 실험하는 것이다.
    """
    flat: FlatMatrix = []
    for row in matrix:
        for value in row:
            flat.append(value)
    return flat


def mac_score(pattern: Matrix, filter_matrix: Matrix) -> float:
    """기본 2차원 배열 기반 MAC 연산.

    MAC(Multiply-Accumulate)란?
    같은 위치끼리 곱하고(Multiply), 그 결과를 전부 더하는(Accumulate) 연산.

    예)
    pattern[row][col] * filter[row][col] 를 전부 더함.

    수식으로 쓰면:
    score = Σ(pattern[i][j] * filter[i][j])

    이 함수는 과제 문서의 핵심 요구사항이다.
    외부 라이브러리 없이 반복문으로 직접 구현했다.
    """
    size = len(pattern)
    total = 0.0
    for row in range(size):
        for col in range(size):
            total += pattern[row][col] * filter_matrix[row][col]
    return total


def mac_score_flat(pattern_flat: FlatMatrix, filter_flat: FlatMatrix) -> float:
    """1차원 배열 기반 MAC 연산.

    논리는 mac_score와 완전히 같다.
    단지 2중 인덱싱 대신 1중 인덱싱만 사용한다.
    """
    total = 0.0
    length = len(pattern_flat)
    for index in range(length):
        total += pattern_flat[index] * filter_flat[index]
    return total


# -----------------------------------------------------------------------------
# 점수 비교 / 판정 함수
# -----------------------------------------------------------------------------
def judge_from_scores(score_cross: float, score_x: float, epsilon: float = EPSILON) -> str:
    """Cross 점수와 X 점수를 비교해 최종 판정을 내린다.

    과제 규칙:
    - 두 점수 차이가 epsilon보다 작으면 동점 취급 -> UNDECIDED
    - Cross가 더 크면 Cross
    - X가 더 크면 X

    왜 epsilon이 필요한가?
    부동소수점 계산에서는 0.9와 0.899999999999 같은 식으로
    사람이 보기엔 같은데 컴퓨터 내부 표현상 아주 미세한 차이가 날 수 있다.
    그래서 '정확히 같다' 대신 '충분히 가깝다'를 써야 한다.
    """
    diff = score_cross - score_x
    if abs(diff) < epsilon:
        return UNDECIDED
    if diff > 0:
        return STANDARD_CROSS
    return STANDARD_X


def judge_ab(score_a: float, score_b: float, epsilon: float = EPSILON) -> str:
    """모드 1 전용 판정 함수.

    모드 1에서는 필터 이름이 Cross/X가 아니라
    단순히 A, B 이므로 출력도 A/B/판정 불가로 한다.
    """
    diff = score_a - score_b
    if abs(diff) < epsilon:
        return "판정 불가"
    if diff > 0:
        return "A"
    return "B"


# -----------------------------------------------------------------------------
# 성능 측정 함수
# -----------------------------------------------------------------------------
def average_ms(operation: Callable[[], Any], repeat: int) -> float:
    """함수(operation)를 repeat번 실행한 평균 시간을 ms 단위로 반환한다.

    측정 포인트
    - I/O 시간 제외
    - 순수 계산 함수 호출 구간만 측정

    perf_counter_ns()를 써서 ns(나노초) 정밀도로 측정한 뒤,
    마지막에 ms(밀리초)로 변환한다.
    """
    if repeat <= 0:
        raise ValueError("repeat는 1 이상이어야 합니다.")

    start_ns = perf_counter_ns()
    for _ in range(repeat):
        operation()
    elapsed_ns = perf_counter_ns() - start_ns
    return (elapsed_ns / repeat) / 1_000_000.0


# -----------------------------------------------------------------------------
# 패턴 생성 함수 (보너스 2)
# -----------------------------------------------------------------------------
def generate_cross_pattern(size: int, on_value: float = 1.0, off_value: float = 0.0) -> Matrix:
    """NxN Cross(십자가) 패턴을 자동 생성한다.

    Cross 규칙
    - 가운데 행 전체 = 1
    - 가운데 열 전체 = 1
    - 나머지 = 0

    예: 5x5
    0 0 1 0 0
    0 0 1 0 0
    1 1 1 1 1
    0 0 1 0 0
    0 0 1 0 0
    """
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
    """NxN X 패턴을 자동 생성한다.

    X 규칙
    - 주대각선(row == col) = 1
    - 부대각선(row + col == size - 1) = 1
    - 나머지 = 0
    """
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
    """두 행렬을 가중합으로 섞는다.

    이 함수는 주로 성능 측정용 '테스트 입력'을 만들기 위해 사용한다.
    예를 들어 Cross 70%, X 30%처럼 섞은 행렬을 만들어서
    지나치게 단순하지 않은 입력으로 벤치마크한다.
    """
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


# -----------------------------------------------------------------------------
# 행렬 출력 보조 함수
# -----------------------------------------------------------------------------
def matrix_to_pretty_lines(matrix: Matrix) -> List[str]:
    """행렬을 사람이 읽기 좋은 문자열 리스트로 변환한다."""
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
    """행렬 이름과 내용을 콘솔에 출력한다."""
    print(name)
    for line in matrix_to_pretty_lines(matrix):
        print(line)


# -----------------------------------------------------------------------------
# 콘솔 입력 관련 함수 (모드 1)
# -----------------------------------------------------------------------------
def parse_console_row(line: str, size: int) -> List[float]:
    """사용자가 입력한 한 줄을 size개의 숫자 행으로 변환한다.

    예: "0 1 0" -> [0.0, 1.0, 0.0]

    검증 내용
    - 공백 기준으로 size개가 들어왔는지
    - 각 항목이 숫자로 변환 가능한지
    """
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
    """콘솔에서 size x size 행렬을 입력받는다.

    사용자가 중간에 한 줄이라도 잘못 입력하면
    과제 요구사항에 맞게 안내 문구를 보여주고 처음부터 다시 입력받는다.
    """
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
                print("처음부터 다시 입력해주세요.")
                failed = True
                break
            rows.append(row)

        if not failed and len(rows) == size:
            return rows


# -----------------------------------------------------------------------------
# 출력 꾸미기
# -----------------------------------------------------------------------------
def print_divider(title: str) -> None:
    """콘솔에서 섹션 구분선 역할을 하는 함수."""
    print("" + "#" * 34)
    print(f"# {title}")
    print("#" * 34)


# -----------------------------------------------------------------------------
# 벤치마크 관련 함수
# -----------------------------------------------------------------------------
def benchmark_single_input(pattern: Matrix, filter_matrix: Matrix, repeat: int) -> BenchmarkResult:
    """입력 1개에 대해 기본 방식과 최적화 방식을 모두 측정한다."""
    size = len(pattern)
    pattern_flat = flatten_matrix(pattern)
    filter_flat = flatten_matrix(filter_matrix)

    basic_ms = average_ms(lambda: mac_score(pattern, filter_matrix), repeat)
    optimized_ms = average_ms(lambda: mac_score_flat(pattern_flat, filter_flat), repeat)
    return BenchmarkResult(
        size=size,
        basic_ms=basic_ms,
        optimized_ms=optimized_ms,
        operations=size * size,   # MAC에서 위치별 곱셈 횟수 = N^2
    )


def benchmark_sizes(sizes: Sequence[int], repeat: int) -> List[BenchmarkResult]:
    """여러 크기에 대해 성능 측정을 수행한다.

    과제 문서의 예시 크기: 3, 5, 13, 25
    각 크기별로 Cross/X를 섞은 probe 입력을 만들어 측정한다.
    """
    results: List[BenchmarkResult] = []
    for size in sizes:
        cross = generate_cross_pattern(size)
        x_pattern = generate_x_pattern(size)
        probe = blend_matrices(cross, x_pattern, 0.7, 0.3)
        results.append(benchmark_single_input(probe, cross, repeat))
    return results


def print_benchmark_table(results: Sequence[BenchmarkResult], repeat: int) -> None:
    """성능 분석 표를 출력한다."""
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


# -----------------------------------------------------------------------------
# JSON 로드 / 필터 검증 관련 함수 (모드 2)
# -----------------------------------------------------------------------------
def load_json_file(path: Path) -> Dict[str, Any]:
    """JSON 파일을 읽어서 dict로 반환한다."""
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 구조는 객체(dict)여야 합니다.")
    return data


def load_filter_sets(filters_obj: Any) -> Tuple[Dict[int, Dict[str, Matrix]], List[str]]:
    """JSON의 filters 영역을 읽어 내부 구조로 변환한다.

    반환값
    - filter_sets:
        {
            5:  {"Cross": [...], "X": [...]},
            13: {"Cross": [...], "X": [...]},
            25: {"Cross": [...], "X": [...]}
        }
    - errors: 필터 로드 중 발견된 경고/오류 메시지 목록

    주의
    - 필터 오류가 일부 있어도 가능한 것은 계속 진행하고,
      오류 메시지를 모아서 출력한다.
    - 과제 요구사항에 따라 프로그램 전체가 중간 종료되지 않도록 설계했다.
    """
    errors: List[str] = []
    filter_sets: Dict[int, Dict[str, Matrix]] = {}

    if not isinstance(filters_obj, dict):
        raise ValueError("filters는 객체(dict)여야 합니다.")

    for size_key, raw_group in filters_obj.items():
        # size_5, size_13, size_25 형식 검사
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

        # Cross, X 둘 다 있어야 완전한 필터 세트로 인정
        missing = [label for label in (STANDARD_CROSS, STANDARD_X) if label not in normalized_group]
        if missing:
            errors.append(f"filters.{size_key}: 필요한 필터가 없습니다 -> {', '.join(missing)}")
            continue

        filter_sets[size] = normalized_group

    return filter_sets, errors


# -----------------------------------------------------------------------------
# 패턴 케이스 분석 관련 함수
# -----------------------------------------------------------------------------
def sort_case_id(case_id: str) -> Tuple[int, str]:
    """케이스를 size 기준으로 보기 좋게 정렬하기 위한 키 함수."""
    match = PATTERN_KEY_RE.match(case_id)
    if match is None:
        return (10**9, case_id)
    return (int(match.group(1)), case_id)


def analyze_case(case_id: str, case_obj: Any, filter_sets: Dict[int, Dict[str, Matrix]]) -> CaseResult:
    """JSON 패턴 1개를 분석해서 CaseResult를 반환한다.

    이 함수 안에서 하는 일
    1. case_id 형식 검사 (size_N_idx)
    2. input / expected 존재 여부 검사
    3. input 행렬 검증
    4. expected 라벨 정규화
    5. 해당 크기의 필터 찾기
    6. Cross, X 각각 MAC 점수 계산
    7. epsilon 기반 최종 판정
    8. expected와 비교해 PASS/FAIL 결정

    중요한 점
    - 오류가 나도 예외를 바깥으로 던져 프로그램을 죽이지 않고,
      CaseResult(passed=False, reason=...) 형태로 반환한다.
    - 즉, '케이스 단위 FAIL 처리'를 구현한 부분이다.
    """
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

    # 실제 점수 계산
    cross_score = mac_score(pattern, cross_filter)
    x_score = mac_score(pattern, x_filter)

    # 점수 비교 -> Cross/X/UNDECIDED
    predicted = judge_from_scores(cross_score, x_score)

    # 정답과 비교해서 PASS/FAIL 결정
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


# -----------------------------------------------------------------------------
# 모드 2 실행 함수
# -----------------------------------------------------------------------------
def analyze_json_cases(path: Path, repeat: int) -> int:
    """JSON 분석 모드 전체 흐름을 담당한다.

    순서
    [1] JSON 로드 및 필터 로드
    [2] 패턴 분석 및 PASS/FAIL 출력
    [3] 성능 분석 표 출력
    [4] 총합 요약 출력
    """
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
        print("[필터 경고/오류]")
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
    print_benchmark_table(benchmark_results, repeat) #모드 2에 성능 분석

    print_divider("[4] 결과 요약")
    total = len(results)
    passed_count = sum(1 for item in results if item.passed)
    failed_results = [item for item in results if not item.passed]

    print(f"총 테스트: {total}개")
    print(f"통과: {passed_count}개")
    print(f"실패: {len(failed_results)}개")

    if failed_results:
        print("실패 케이스:")
        for item in failed_results:
            summary = item.reason or "원인 미상"
            print(f"- {item.case_id}: {summary}")

    return 0


# -----------------------------------------------------------------------------
# 모드 1 실행 함수
# -----------------------------------------------------------------------------
def run_interactive_mode(repeat: int, epsilon: float) -> int:
    """사용자 입력(3x3) 모드 실행 함수.

    흐름
    [1] 필터 A, 필터 B 입력
    [2] 패턴 입력
    [3] A/B 점수 계산 및 판정
    [4] 성능 분석(기본 vs 최적화) 출력
    """
    print_divider("[1] 필터 입력")
    filter_a = read_matrix_from_console(3, "필터 A (3줄 입력, 공백 구분)")
    print()
    filter_b = read_matrix_from_console(3, "필터 B (3줄 입력, 공백 구분)")

    print("저장된 필터")
    print_matrix("A", filter_a)
    print()
    print_matrix("B", filter_b)

    print_divider("[2] 패턴 입력")
    pattern = read_matrix_from_console(3, "패턴 (3줄 입력, 공백 구분)")
    print()
    print_matrix("입력 패턴", pattern)

    # A, B 각각과 MAC 점수 계산
    score_a = mac_score(pattern, filter_a)
    score_b = mac_score(pattern, filter_b)
    decision = judge_ab(score_a, score_b, epsilon)

    # 성능 측정: 2차원 방식
    pair_basic_ms = average_ms(lambda: (mac_score(pattern, filter_a), mac_score(pattern, filter_b)), repeat)

    # 성능 측정: 1차원 방식
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


# -----------------------------------------------------------------------------
# 보너스 패턴 생성 출력 함수
# -----------------------------------------------------------------------------
def print_generated_patterns(size: int) -> None:
    """--generate 옵션으로 생성한 Cross/X 패턴을 출력한다."""
    cross = generate_cross_pattern(size)
    x_pattern = generate_x_pattern(size)
    print(f"자동 생성 패턴 (크기: {size}x{size})")
    print_matrix(f"{STANDARD_CROSS} 패턴", cross)
    print()
    print_matrix(f"{STANDARD_X} 패턴", x_pattern)


# -----------------------------------------------------------------------------
# argparse 설정
# -----------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    """명령줄 옵션 파서를 만든다.

    지원 옵션
    - --mode interactive/json/1/2
    - --data data.json 경로
    - --repeat 성능 측정 반복 횟수
    - --epsilon 동점 허용 오차
    - --generate N  (보너스 패턴 생성)
    """
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


# -----------------------------------------------------------------------------
# 실행 모드 선택
# -----------------------------------------------------------------------------
def ask_mode_interactively() -> str:
    """명령줄 옵션이 없을 때 콘솔에서 1번/2번 모드를 직접 선택하게 한다."""
    print("=== Mini NPU Simulator ===")
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")

    while True:
        choice = input("선택: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("1 또는 2를 입력해주세요.")


# -----------------------------------------------------------------------------
# 메인 함수
# -----------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    """프로그램 진입점.

    전체 실행 흐름
    1. 명령줄 인자 파싱
    2. repeat / epsilon 유효성 검사
    3. --generate가 있으면 패턴 생성만 하고 종료
    4. mode 결정
    5. interactive면 모드 1 실행
    6. json이면 모드 2 실행
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # 방어 코드: 반복 횟수는 1 이상이어야 한다.
    if args.repeat <= 0:
        print("--repeat 값은 1 이상이어야 합니다.")
        return 1

    # 방어 코드: epsilon은 음수가 될 수 없다.
    if args.epsilon < 0:
        print("--epsilon 값은 0 이상이어야 합니다.")
        return 1

    # 사용자가 --epsilon으로 값을 바꾸면 전역 EPSILON도 함께 갱신한다.
    global EPSILON
    EPSILON = args.epsilon

    # 보너스 패턴 생성 기능은 다른 흐름보다 먼저 처리한다.
    if args.generate is not None:
        print_generated_patterns(args.generate)
        return 0

    # mode를 안 주면 실행 중 직접 선택
    mode = args.mode or ask_mode_interactively()
    if mode == "1":
        mode = "interactive"
    elif mode == "2":
        mode = "json"

    if mode == "interactive":
        return run_interactive_mode(args.repeat, args.epsilon)

    data_path = Path(args.data)
    return analyze_json_cases(data_path, args.repeat)


# 파이썬 파일을 직접 실행했을 때만 main() 호출
if __name__ == "__main__":
    sys.exit(main())
