"""로컬 README의 SVG 카드 전용 구성을 검사한다. 네트워크/파일 변경은 하지 않는다."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

MAX_BYTES = 1_048_576
ALLOWED_TAGS = {"div", "p", "a", "img", "br"}
SVG_NS = "http://www.w3.org/2000/svg"


class ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[dict[str, str | None]] = []
        self.text: list[str] = []
        self.other_tags: set[str] = set()
        self.duplicate_image_attrs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self.other_tags.add(tag)
        if tag == "img":
            # Keep the first attribute, as HTML does, and reject ambiguity.
            image: dict[str, str | None] = {}
            for name, value in attrs:
                if name in image:
                    self.duplicate_image_attrs.add(name)
                else:
                    image[name] = value
            self.images.append(image)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data.strip())


def read_limited(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("파일 크기가 1 MiB를 초과합니다.")
    return raw.decode("utf-8-sig")


def local_svg(root: Path, source: str) -> Path:
    url = urlsplit(source)
    if url.scheme or url.netloc or not url.path or "\\" in source:
        raise ValueError("이미지는 저장소 내부의 상대 경로여야 합니다.")
    decoded = unquote(url.path)
    if "\\" in decoded or Path(decoded).is_absolute():
        raise ValueError("절대 경로와 역슬래시 경로는 지원하지 않습니다.")
    path = (root / decoded).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("이미지 경로가 저장소 밖을 가리킵니다.") from exc
    if path.suffix.lower() != ".svg":
        raise ValueError("SVG 카드만 허용합니다.")
    return path


def animation_evidence(text: str) -> list[str]:
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("DTD와 엔티티 선언을 포함한 SVG는 지원하지 않습니다.")
    svg = ET.fromstring(text)
    if svg.tag != f"{{{SVG_NS}}}svg":
        raise ValueError("SVG 루트와 네임스페이스가 올바르지 않습니다.")
    evidence: set[str] = set()
    for element in svg.iter():
        tag = element.tag
        if tag in {f"{{{SVG_NS}}}{name}" for name in ("animate", "animateTransform", "animateMotion", "set")}:
            evidence.add(tag.rsplit("}", 1)[-1])
        if tag == f"{{{SVG_NS}}}style":
            css = "".join(element.itertext())
            if re.search(r"@keyframes\b", css, flags=re.IGNORECASE | re.ASCII):
                evidence.add("css-keyframes")
    return sorted(evidence)


def audit_profile(directory: Path, expected_images: int | None = None) -> dict[str, Any]:
    if expected_images is not None and expected_images < 1:
        raise ValueError("예상 이미지 수는 1 이상이어야 합니다.")
    root = directory.resolve()
    findings: list[str] = []
    records: list[dict[str, Any]] = []
    parser = ProfileParser()
    try:
        readme = (root / "README.md").resolve()
        readme.relative_to(root)
        parser.feed(read_limited(readme))
        parser.close()
    except (OSError, UnicodeError, ValueError) as exc:
        findings.append(f"README 읽기 실패: {exc}")
    if parser.text:
        findings.append("이미지 밖에 정적 텍스트가 있습니다.")
    if parser.other_tags:
        findings.append("허용하지 않는 HTML 태그: " + ", ".join(sorted(parser.other_tags)))
    if parser.duplicate_image_attrs:
        findings.append("중복 이미지 속성: " + ", ".join(sorted(parser.duplicate_image_attrs)))
    if not parser.images:
        findings.append("이미지 카드가 없습니다.")
    if expected_images is not None and len(parser.images) != expected_images:
        findings.append(f"이미지 개수 불일치: 예상 {expected_images}, 실제 {len(parser.images)}")
    for image in parser.images:
        source = image.get("src") or ""
        record: dict[str, Any] = {"source": source, "animation_evidence": []}
        if not (image.get("alt") or "").strip():
            findings.append(f"대체 텍스트가 없습니다: {source}")
        try:
            text = read_limited(local_svg(root, source))
            record["animation_evidence"] = animation_evidence(text)
            if not record["animation_evidence"]:
                findings.append(f"애니메이션 선언을 찾지 못했습니다: {source}")
        except (OSError, UnicodeError, ValueError, ET.ParseError) as exc:
            findings.append(f"이미지 검사 실패 ({source}): {exc}")
        records.append(record)
    return {"ok": not findings, "image_count": len(parser.images), "images": records,
            "findings": findings, "browser_animation_verified": False}


def positive_count(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="검사할 프로필 저장소의 로컬 경로")
    parser.add_argument("--expected-images", type=positive_count)
    args = parser.parse_args(argv)
    result = audit_profile(args.directory, args.expected_images)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
