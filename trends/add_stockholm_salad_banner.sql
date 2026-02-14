-- 스톡홀름샐러드 정문점 배너 추가 SQL 쿼리
-- 테이블명: trends_trend

-- PostgreSQL / MySQL / SQLite 공통 버전
INSERT INTO trends_trend (title, description, image, blog_link, created_at, updated_at)
VALUES (
    '스톡홀름샐러드 정문점에서',
    '아메리카노 단돈 천원 이벤트를 진행하고 있어요',
    'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png',
    'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m',
    NOW(),
    NOW()
);

-- PostgreSQL 특화 버전 (타임존 명시)
-- INSERT INTO trends_trend (title, description, image, blog_link, created_at, updated_at)
-- VALUES (
--     '스톡홀름샐러드 정문점에서',
--     '아메리카노 단돈 천원 이벤트를 진행하고 있어요',
--     'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png',
--     'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m',
--     CURRENT_TIMESTAMP,
--     CURRENT_TIMESTAMP
-- );

-- MySQL 특화 버전
-- INSERT INTO trends_trend (title, description, image, blog_link, created_at, updated_at)
-- VALUES (
--     '스톡홀름샐러드 정문점에서',
--     '아메리카노 단돈 천원 이벤트를 진행하고 있어요',
--     'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png',
--     'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m',
--     NOW(),
--     NOW()
-- );

-- SQLite 특화 버전
-- INSERT INTO trends_trend (title, description, image, blog_link, created_at, updated_at)
-- VALUES (
--     '스톡홀름샐러드 정문점에서',
--     '아메리카노 단돈 천원 이벤트를 진행하고 있어요',
--     'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/StockholmSalad/StockholmSaladbanner.png',
--     'https://www.instagram.com/stock_truedoor?igsh=ajF4aWlvZnZuOW1m',
--     datetime('now'),
--     datetime('now')
-- );













