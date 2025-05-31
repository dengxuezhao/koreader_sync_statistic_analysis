-- Kompanion Python PostgreSQL初始化脚本

-- 创建必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于全文搜索
CREATE EXTENSION IF NOT EXISTS "unaccent"; -- 用于忽略重音符号的搜索

-- 设置默认编码和排序规则
ALTER DATABASE kompanion SET timezone TO 'UTC';
ALTER DATABASE kompanion SET default_text_search_config TO 'english';

-- 创建索引函数（用于不区分大小写的搜索）
CREATE OR REPLACE FUNCTION f_unaccent(text)
  RETURNS text AS
$func$
SELECT unaccent('unaccent', $1)  -- schema-qualify function and dictionary
$func$  LANGUAGE sql IMMUTABLE;

-- 创建管理员用户（如果不存在）
DO $$
BEGIN
    -- 这里可以添加创建默认管理员用户的逻辑
    -- 实际的用户创建将由应用程序处理
    RAISE NOTICE '数据库初始化完成。请使用应用程序脚本创建管理员用户。';
END $$; 