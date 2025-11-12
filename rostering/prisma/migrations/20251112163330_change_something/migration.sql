-- DropIndex
DROP INDEX "external_requests_id_idx";

-- CreateIndex
CREATE INDEX "external_requests_id_idx" ON "external_requests"("id" varchar_pattern_ops);
