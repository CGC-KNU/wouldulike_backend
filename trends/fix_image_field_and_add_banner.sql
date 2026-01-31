-- 1단계: image 필드 길이 확장 (VARCHAR(100) -> VARCHAR(500))
-- PostgreSQL
ALTER TABLE trends_trend ALTER COLUMN image TYPE VARCHAR(500);

-- 또는 더 긴 URL을 위해 TEXT 타입으로 변경 (권장)
-- ALTER TABLE trends_trend ALTER COLUMN image TYPE TEXT;

-- 2단계: 배너 추가
INSERT INTO trends_trend (title, description, image, blog_link, created_at, updated_at)
VALUES (
    '스톡홀름샐러드 정문점에서',
    '아메리카노 단돈 천원 이벤트를 진행하고 있어요',
    'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png',
    'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m',
    NOW(),
    NOW()
);













