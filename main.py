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
