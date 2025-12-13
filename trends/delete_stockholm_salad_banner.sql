-- 스톡홀름샐러드 정문점 배너 삭제 쿼리
-- PostgreSQL / MySQL / SQLite 공통

-- 방법 1: title로 삭제 (권장)
DELETE FROM trends_trend
WHERE title = '스톡홀름샐러드 정문점에서';

-- 방법 2: image URL로 삭제
-- DELETE FROM trends_trend
-- WHERE image = 'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png';

-- 방법 3: blog_link로 삭제
-- DELETE FROM trends_trend
-- WHERE blog_link = 'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m';

-- 방법 4: 여러 조건 조합 (가장 안전)
-- DELETE FROM trends_trend
-- WHERE title = '스톡홀름샐러드 정문점에서'
--   AND image = 'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png'
--   AND blog_link = 'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m';

-- 삭제 전 확인 쿼리 (실행 전에 먼저 확인)
-- SELECT * FROM trends_trend
-- WHERE title = '스톡홀름샐러드 정문점에서';







