## 입력 CSV 스키마

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|:--:|---|
| `date` | YYYY-MM-DD | ✅ | 성과 발생 날짜 |
| `channel` | 문자 | ✅ | instagram, naver_blog, youtube, kakao, google_ads, facebook |
| `content_id` | 문자 | ✅ | 콘텐츠 고유 ID |
| `content_title` | 문자 | ✅ | 콘텐츠 제목 |
| `content_type` | 문자 | ✅ | image, carousel, reels, video, blog_post, story |
| `impressions` | 정수 | ✅ | 노출 |
| `reach` | 정수 | ✅ | 도달 |
| `views` | 정수 | ✅ | 조회수 |
| `clicks` | 정수 | ✅ | 클릭 |
| `inquiries` | 정수 | ✅ | 문의 |
| `conversions` | 정수 | ✅ | 전환 |
| `cost` | 숫자 | ⬜ | 광고비(원). 없으면 CPC/CPA/ROAS 미계산 |
| `revenue` | 숫자 | ⬜ | 매출(원). 없으면 ROAS 미계산 |

1행 = **하루 × 채널 × 콘텐츠** 단위 성과입니다.
퍼널 논리상 `노출 ≥ 도달 ≥ 조회수 ≥ 클릭 ≥ 문의 ≥ 전환` 이어야 하며, 어긋난 행이 있어도 **경고만 표시하고 분석은 계속**합니다. (실무 데이터는 채널별 집계 기준이 달라 자주 깨집니다)
