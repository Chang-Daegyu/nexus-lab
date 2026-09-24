# nexus-lab

## Profile Guard

프로필 README에 정적 설명·수상 목록·외부 Stats 이미지가 섞였는지 검사하는 **읽기 전용 명령행 도구**입니다. HTML로 연결한 로컬 SVG 카드 전용 README를 대상으로 합니다.

### 실행

Python 3.10 이상에서 외부 패키지나 API 키 없이 실행합니다.

```sh
python profile_guard.py ../Chang-Daegyu --expected-images 6
python -m unittest discover -s tests -v
```

검사가 통과하면 종료 코드 `0`, 문제가 있으면 `1`을 반환합니다. 옵션 사용 오류는 `2`입니다. 결과는 JSON으로 출력하며, 파일을 수정하거나 네트워크 요청을 보내지 않습니다.

### 검사 항목

- 이미지 밖의 정적 텍스트와 허용하지 않은 HTML 태그
- 예상 카드 개수, 이미지 대체 텍스트, SVG 파일 존재 여부
- 저장소를 벗어나는 경로, 외부 이미지 주소, 비정상 XML
- SVG의 SMIL 애니메이션 선언 또는 CSS `@keyframes` 선언

### 범위와 한계

이 도구는 범용 Markdown 렌더러나 완전한 HTML 검증기가 아닙니다. 허용 태그는 `div`, `p`, `a`, `img`, `br`입니다. 이미지 Markdown 문법 대신 HTML `img`를 사용합니다.

애니메이션 **선언**을 찾는 것과 브라우저에서 실제로 움직이는 것을 확인하는 것은 다릅니다. 출력의 `browser_animation_verified`는 항상 `false`입니다. 주석 안의 CSS 선언 등으로 인한 탐지 오차가 있을 수 있으며, 실제 GitHub 렌더링·CSS 적용·브라우저 동작은 별도로 확인해야 합니다.

GitHub Achievement 발급이나 등급 변경 기능은 없습니다. PR 수를 배지 획득 여부로 간주하지 않습니다.

### 검증

외부 API 없는 회귀 테스트 25개를 포함합니다. 로컬에서 `python -m unittest discover -s tests -v`로 실행했습니다. 심볼릭 링크 테스트는 해당 기능이 없는 환경에서 건너뜁니다. GitHub Actions 워크플로는 추가하지 않았습니다.
