-- CreateEnum
CREATE TYPE "RosterStrategy" AS ENUM ('CONTINUITY', 'TRAVEL', 'BALANCED');

-- CreateEnum
CREATE TYPE "RosterStatus" AS ENUM ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'PUBLISHED', 'ACTIVE', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "AssignmentStatus" AS ENUM ('PENDING', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "PublicationStatus" AS ENUM ('ACTIVE', 'COMPLETED', 'EXPIRED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "AcceptanceStatus" AS ENUM ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'ESCALATED');

-- CreateEnum
CREATE TYPE "LocationStatus" AS ENUM ('ON_TIME', 'RUNNING_LATE', 'OVERDUE', 'UPCOMING', 'COMPLETED', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "LatenessReason" AS ENUM ('TRAFFIC', 'PREVIOUS_OVERRUN', 'DISTANCE', 'EMERGENCY', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "AlertStatus" AS ENUM ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED');

-- CreateEnum
CREATE TYPE "IncidentType" AS ENUM ('FALL', 'MEDICATION_ERROR', 'EQUIPMENT_FAILURE', 'SAFEGUARDING', 'DELAY', 'MISSED_VISIT', 'CLIENT_COMPLAINT', 'OTHER');

-- CreateEnum
CREATE TYPE "IncidentSeverity" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- CreateEnum
CREATE TYPE "IncidentStatus" AS ENUM ('REPORTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'ESCALATED');

-- CreateEnum
CREATE TYPE "DisruptionType" AS ENUM ('CARER_SICK', 'CARER_UNAVAILABLE', 'VISIT_CANCELLED', 'EMERGENCY_VISIT', 'DELAY', 'EQUIPMENT_FAILURE', 'WEATHER', 'TRANSPORT_ISSUE', 'OTHER');

-- CreateEnum
CREATE TYPE "DisruptionSeverity" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- CreateEnum
CREATE TYPE "DisruptionStatus" AS ENUM ('REPORTED', 'ACKNOWLEDGED', 'ANALYZING', 'RESOLVING', 'RESOLVED', 'ESCALATED');

-- CreateEnum
CREATE TYPE "TimesheetStatus" AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'PROCESSED');

-- CreateEnum
CREATE TYPE "ExceptionType" AS ENUM ('MISSING_CHECK_OUT', 'SHORT_VISIT', 'LONG_VISIT', 'OUTSIDE_GEOFENCE', 'MISSING_TASKS', 'TIME_CONFLICT', 'OVERTIME_EXCEEDED', 'OTHER');

-- CreateEnum
CREATE TYPE "ExceptionSeverity" AS ENUM ('INFO', 'WARNING', 'ERROR', 'CRITICAL');

-- CreateEnum
CREATE TYPE "ExceptionStatus" AS ENUM ('PENDING', 'ACKNOWLEDGED', 'RESOLVED', 'ESCALATED');

-- CreateEnum
CREATE TYPE "AdjustmentType" AS ENUM ('MANUAL_CORRECTION', 'OVERTIME_APPROVAL', 'BONUS', 'DEDUCTION', 'MILEAGE', 'EXPENSE', 'OTHER');

-- CreateEnum
CREATE TYPE "InvoiceStatus" AS ENUM ('DRAFT', 'SENT', 'VIEWED', 'PAID', 'OVERDUE', 'CANCELLED', 'PARTIAL');

-- CreateEnum
CREATE TYPE "PayrollStatus" AS ENUM ('PROCESSING', 'PENDING_APPROVAL', 'APPROVED', 'EXPORTED', 'COMPLETED', 'FAILED');

-- CreateEnum
CREATE TYPE "PayslipStatus" AS ENUM ('GENERATED', 'SENT', 'VIEWED', 'ACKNOWLEDGED');

-- CreateEnum
CREATE TYPE "ComplianceReportType" AS ENUM ('WTD_COMPLIANCE', 'REST_PERIOD', 'VISIT_PUNCTUALITY', 'CONTINUITY', 'SKILL_COVERAGE', 'TIMESHEET_ACCURACY', 'FINANCIAL_SUMMARY');

-- CreateEnum
CREATE TYPE "ReportStatus" AS ENUM ('GENERATING', 'COMPLETED', 'FAILED');

-- AlterTable
ALTER TABLE "clusters" ADD COLUMN     "location" TEXT;

-- DropEnum
DROP TYPE "CommunicationMethod";

-- CreateTable
CREATE TABLE "rostering_constraints" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "name" TEXT NOT NULL DEFAULT 'Default Rules',
    "wtd_max_hours_per_week" INTEGER NOT NULL DEFAULT 48,
    "rest_period_hours" INTEGER NOT NULL DEFAULT 11,
    "buffer_minutes" INTEGER NOT NULL DEFAULT 5,
    "travel_max_minutes" INTEGER NOT NULL DEFAULT 20,
    "continuity_target_percent" INTEGER NOT NULL DEFAULT 85,
    "max_daily_hours" INTEGER DEFAULT 10,
    "min_rest_between_visits" INTEGER DEFAULT 0,
    "max_travel_time_per_visit" INTEGER DEFAULT 60,
    "is_active" BOOLEAN DEFAULT true,
    "created_by" TEXT,
    "updated_by" TEXT,
    "updated_by_email" TEXT,
    "updated_by_first_name" TEXT,
    "updated_by_last_name" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "rostering_constraints_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "travel_matrix_cache" (
    "id" TEXT NOT NULL,
    "from_postcode" TEXT NOT NULL,
    "to_postcode" TEXT NOT NULL,
    "distance_meters" INTEGER,
    "duration_seconds" INTEGER,
    "traffic_duration_seconds" INTEGER,
    "mode" TEXT NOT NULL DEFAULT 'driving',
    "calculated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "travel_matrix_cache_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "rosters" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "strategy" "RosterStrategy" NOT NULL DEFAULT 'BALANCED',
    "start_date" TIMESTAMP(3) NOT NULL,
    "end_date" TIMESTAMP(3) NOT NULL,
    "created_by" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "status" "RosterStatus" NOT NULL DEFAULT 'DRAFT',
    "published_at" TIMESTAMP(3),
    "total_assignments" INTEGER NOT NULL DEFAULT 0,
    "total_travel_minutes" INTEGER NOT NULL DEFAULT 0,
    "continuity_score" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "quality_score" DOUBLE PRECISION NOT NULL DEFAULT 0,

    CONSTRAINT "rosters_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "assignments" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "roster_id" TEXT NOT NULL,
    "visit_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "scheduled_time" TIMESTAMP(3) NOT NULL,
    "estimated_end_time" TIMESTAMP(3) NOT NULL,
    "actual_duration" INTEGER,
    "travel_from_previous" INTEGER NOT NULL DEFAULT 0,
    "travel_distance" DOUBLE PRECISION,
    "wtd_compliant" BOOLEAN NOT NULL DEFAULT true,
    "rest_period_ok" BOOLEAN NOT NULL DEFAULT true,
    "travel_time_ok" BOOLEAN NOT NULL DEFAULT true,
    "skills_match" BOOLEAN NOT NULL DEFAULT true,
    "warnings" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "status" "AssignmentStatus" NOT NULL DEFAULT 'PENDING',
    "accepted_at" TIMESTAMP(3),
    "declined_at" TIMESTAMP(3),
    "decline_reason" TEXT,
    "locked" BOOLEAN NOT NULL DEFAULT false,
    "locked_reason" TEXT,
    "locked_by" TEXT,
    "locked_at" TIMESTAMP(3),
    "manually_assigned" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "assignments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carer_location_updates" (
    "id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION NOT NULL,
    "longitude" DOUBLE PRECISION NOT NULL,
    "accuracy" DOUBLE PRECISION NOT NULL,
    "location" geography(POINT, 4326),
    "current_visit_id" TEXT,
    "status" "LocationStatus" NOT NULL DEFAULT 'UNKNOWN',
    "recorded_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "carer_location_updates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "visit_check_ins" (
    "id" TEXT NOT NULL,
    "visit_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION NOT NULL,
    "longitude" DOUBLE PRECISION NOT NULL,
    "within_geofence" BOOLEAN NOT NULL DEFAULT true,
    "distance" DOUBLE PRECISION NOT NULL,
    "check_in_time" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "notes" TEXT,
    "requires_approval" BOOLEAN NOT NULL DEFAULT false,
    "approved_by" TEXT,
    "approved_at" TIMESTAMP(3),

    CONSTRAINT "visit_check_ins_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "visit_check_outs" (
    "id" TEXT NOT NULL,
    "visit_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION NOT NULL,
    "longitude" DOUBLE PRECISION NOT NULL,
    "check_out_time" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "actual_duration" INTEGER NOT NULL,
    "tasks_completed" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "incident_reported" BOOLEAN NOT NULL DEFAULT false,
    "incident_details" TEXT,
    "incident_severity" "IncidentSeverity",
    "notes" TEXT,

    CONSTRAINT "visit_check_outs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "lateness_alerts" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "visit_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "scheduled_time" TIMESTAMP(3) NOT NULL,
    "estimated_arrival" TIMESTAMP(3) NOT NULL,
    "delay_minutes" INTEGER NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "reason" "LatenessReason" NOT NULL DEFAULT 'UNKNOWN',
    "details" TEXT,
    "status" "AlertStatus" NOT NULL DEFAULT 'ACTIVE',
    "resolved_at" TIMESTAMP(3),
    "resolution" TEXT,
    "client_notified" BOOLEAN NOT NULL DEFAULT false,
    "swap_suggested" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "lateness_alerts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "incidents" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "visit_id" TEXT,
    "carer_id" TEXT,
    "client_id" TEXT,
    "type" "IncidentType" NOT NULL,
    "severity" "IncidentSeverity" NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "status" "IncidentStatus" NOT NULL DEFAULT 'REPORTED',
    "reported_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reported_by" TEXT NOT NULL,
    "acknowledged_at" TIMESTAMP(3),
    "acknowledged_by" TEXT,
    "resolved_at" TIMESTAMP(3),
    "resolved_by" TEXT,
    "resolution" TEXT,
    "requires_follow_up" BOOLEAN NOT NULL DEFAULT false,
    "follow_up_notes" TEXT,

    CONSTRAINT "incidents_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "assignment_history" (
    "id" TEXT NOT NULL,
    "assignment_id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "change_type" TEXT NOT NULL,
    "previous_carer_id" TEXT,
    "new_carer_id" TEXT,
    "previous_time" TIMESTAMP(3),
    "new_time" TIMESTAMP(3),
    "changed_by" TEXT NOT NULL,
    "changed_by_email" TEXT,
    "reason" TEXT,
    "constraint_overrides" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "assignment_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "travel_matrix" (
    "id" TEXT NOT NULL,
    "from_postcode" TEXT NOT NULL,
    "to_postcode" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL,
    "distance_meters" INTEGER NOT NULL,
    "last_updated" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "travel_matrix_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "visit_eligibility" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "visit_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "eligible" BOOLEAN NOT NULL DEFAULT false,
    "score" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "skills_match" BOOLEAN NOT NULL DEFAULT false,
    "credentials_valid" BOOLEAN NOT NULL DEFAULT false,
    "available" BOOLEAN NOT NULL DEFAULT false,
    "preferences_match" BOOLEAN NOT NULL DEFAULT false,
    "travel_time" INTEGER,
    "last_calculated" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "visit_eligibility_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "roster_versions" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "roster_id" TEXT NOT NULL,
    "version_label" TEXT NOT NULL,
    "published_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "published_by" TEXT NOT NULL,
    "acceptance_deadline" TIMESTAMP(3) NOT NULL,
    "assignments" JSONB NOT NULL,

    CONSTRAINT "roster_versions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carer_notification_preferences" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "preferred_channel" TEXT NOT NULL DEFAULT 'push',
    "best_response_time_start" TEXT,
    "best_response_time_end" TEXT,
    "average_response_time" INTEGER,
    "notification_opt_out" BOOLEAN NOT NULL DEFAULT false,
    "last_notified_at" TIMESTAMP(3),

    CONSTRAINT "carer_notification_preferences_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "escalation_history" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "original_assignment_id" TEXT NOT NULL,
    "escalated_from" TEXT NOT NULL,
    "escalated_to" TEXT NOT NULL,
    "escalation_reason" TEXT NOT NULL,
    "escalated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "escalated_by" TEXT NOT NULL,
    "success" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "escalation_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "cluster_metrics" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "cluster_id" TEXT NOT NULL,
    "calculated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "total_visits" INTEGER NOT NULL DEFAULT 0,
    "total_hours" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "average_distance" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_travel_time" INTEGER NOT NULL DEFAULT 0,
    "skill_coverage" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "continuity_risk" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "required_skills" TEXT[] DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT "cluster_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "roster_publications" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "roster_id" TEXT NOT NULL,
    "version_label" TEXT NOT NULL,
    "published_by" TEXT NOT NULL,
    "published_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "acceptance_deadline" TIMESTAMP(3) NOT NULL,
    "notification_channels" TEXT[] DEFAULT ARRAY['push']::TEXT[],
    "status" "PublicationStatus" NOT NULL DEFAULT 'ACTIVE',
    "completed_at" TIMESTAMP(3),
    "expired_at" TIMESTAMP(3),
    "total_assignments" INTEGER NOT NULL DEFAULT 0,
    "accepted_count" INTEGER NOT NULL DEFAULT 0,
    "declined_count" INTEGER NOT NULL DEFAULT 0,
    "pending_count" INTEGER NOT NULL DEFAULT 0,
    "expired_count" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,
    "metadata" JSONB,
    "auto_escalate" BOOLEAN NOT NULL DEFAULT true,
    "escalation_delay" INTEGER NOT NULL DEFAULT 30,
    "max_escalation_count" INTEGER NOT NULL DEFAULT 3,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "roster_publications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published_assignments" (
    "id" TEXT NOT NULL,
    "publication_id" TEXT NOT NULL,
    "assignment_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "notification_sent_at" TIMESTAMP(3),
    "notification_channel" TEXT,
    "notification_delivered" BOOLEAN NOT NULL DEFAULT false,
    "status" "AcceptanceStatus" NOT NULL DEFAULT 'PENDING',
    "accepted_at" TIMESTAMP(3),
    "accepted_by" TEXT,
    "declined_at" TIMESTAMP(3),
    "decline_reason" TEXT,
    "expired_at" TIMESTAMP(3),
    "escalated_at" TIMESTAMP(3),
    "escalated_to" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "escalation_count" INTEGER NOT NULL DEFAULT 0,
    "viewed_at" TIMESTAMP(3),
    "response_time" INTEGER,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "original_carer_id" TEXT,
    "escalation_level" INTEGER NOT NULL DEFAULT 0,
    "max_escalation_level" INTEGER NOT NULL DEFAULT 3,

    CONSTRAINT "published_assignments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "disruptions" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "type" "DisruptionType" NOT NULL,
    "severity" "DisruptionSeverity" NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "affected_visits" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "affected_carers" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "affected_clients" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "impact_data" JSONB NOT NULL,
    "status" "DisruptionStatus" NOT NULL DEFAULT 'REPORTED',
    "reported_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reported_by" TEXT NOT NULL,
    "acknowledged_at" TIMESTAMP(3),
    "acknowledged_by" TEXT,
    "analyzed_at" TIMESTAMP(3),
    "resolved_at" TIMESTAMP(3),
    "resolved_by" TEXT,
    "resolution" TEXT,
    "resolution_options" JSONB,
    "selected_resolution" TEXT,
    "resolution_applied_at" TIMESTAMP(3),
    "requires_follow_up" BOOLEAN NOT NULL DEFAULT false,
    "follow_up_notes" TEXT,
    "follow_up_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "disruptions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "disruption_actions" (
    "id" TEXT NOT NULL,
    "disruption_id" TEXT NOT NULL,
    "action_type" TEXT NOT NULL,
    "action_data" JSONB NOT NULL,
    "performed_by" TEXT NOT NULL,
    "performed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "success" BOOLEAN NOT NULL DEFAULT true,
    "error_message" TEXT,

    CONSTRAINT "disruption_actions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "timesheets" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "scheduled_hours" DOUBLE PRECISION NOT NULL,
    "actual_hours" DOUBLE PRECISION NOT NULL,
    "overtime_hours" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "break_hours" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "regular_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "overtime_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "status" "TimesheetStatus" NOT NULL DEFAULT 'DRAFT',
    "submitted_at" TIMESTAMP(3),
    "approved_at" TIMESTAMP(3),
    "approved_by" TEXT,
    "rejected_at" TIMESTAMP(3),
    "rejected_by" TEXT,
    "rejection_reason" TEXT,
    "processed_at" TIMESTAMP(3),
    "processed_by" TEXT,
    "payroll_batch_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "timesheets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "timesheet_entries" (
    "id" TEXT NOT NULL,
    "timesheet_id" TEXT NOT NULL,
    "visit_id" TEXT,
    "check_in_time" TIMESTAMP(3) NOT NULL,
    "check_out_time" TIMESTAMP(3),
    "scheduled_start" TIMESTAMP(3) NOT NULL,
    "scheduled_end" TIMESTAMP(3) NOT NULL,
    "scheduled_duration" INTEGER NOT NULL,
    "actual_duration" INTEGER,
    "variance" INTEGER,
    "check_in_location" JSONB,
    "check_out_location" JSONB,
    "within_geofence" BOOLEAN NOT NULL DEFAULT true,
    "tasks_completed" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "notes" TEXT,
    "validated" BOOLEAN NOT NULL DEFAULT false,
    "validated_at" TIMESTAMP(3),
    "validated_by" TEXT,

    CONSTRAINT "timesheet_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "timesheet_exceptions" (
    "id" TEXT NOT NULL,
    "timesheet_id" TEXT NOT NULL,
    "entry_id" TEXT,
    "type" "ExceptionType" NOT NULL,
    "severity" "ExceptionSeverity" NOT NULL,
    "description" TEXT NOT NULL,
    "expected_value" TEXT,
    "actual_value" TEXT,
    "variance" TEXT,
    "status" "ExceptionStatus" NOT NULL DEFAULT 'PENDING',
    "resolved_at" TIMESTAMP(3),
    "resolved_by" TEXT,
    "resolution" TEXT,
    "suggested_action" TEXT,
    "auto_resolvable" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "timesheet_exceptions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "timesheet_adjustments" (
    "id" TEXT NOT NULL,
    "timesheet_id" TEXT NOT NULL,
    "adjustment_type" "AdjustmentType" NOT NULL,
    "description" TEXT NOT NULL,
    "hours_adjustment" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "pay_adjustment" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "reason" TEXT NOT NULL,
    "approved_by" TEXT NOT NULL,
    "approved_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "timesheet_adjustments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoices" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "client_id" TEXT,
    "invoice_number" TEXT NOT NULL,
    "invoice_date" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "due_date" TIMESTAMP(3) NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "subtotal" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "tax_amount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "tax_rate" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_amount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "status" "InvoiceStatus" NOT NULL DEFAULT 'DRAFT',
    "paid_amount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "paid_at" TIMESTAMP(3),
    "purchase_order" TEXT,
    "contract_ref" TEXT,
    "notes" TEXT,
    "terms" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoice_line_items" (
    "id" TEXT NOT NULL,
    "invoice_id" TEXT NOT NULL,
    "visit_id" TEXT,
    "description" TEXT NOT NULL,
    "quantity" DOUBLE PRECISION NOT NULL DEFAULT 1,
    "unit_price" DOUBLE PRECISION NOT NULL,
    "line_total" DOUBLE PRECISION NOT NULL,
    "service_date" TIMESTAMP(3),
    "category" TEXT,

    CONSTRAINT "invoice_line_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoice_payments" (
    "id" TEXT NOT NULL,
    "invoice_id" TEXT NOT NULL,
    "amount" DOUBLE PRECISION NOT NULL,
    "payment_date" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "payment_method" TEXT NOT NULL,
    "reference" TEXT,
    "notes" TEXT,
    "processed_by" TEXT NOT NULL,

    CONSTRAINT "invoice_payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payroll_batches" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "batch_number" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "status" "PayrollStatus" NOT NULL DEFAULT 'PROCESSING',
    "total_gross_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_net_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_tax" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_ni" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_pension" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "employee_count" INTEGER NOT NULL DEFAULT 0,
    "processed_at" TIMESTAMP(3),
    "processed_by" TEXT,
    "approved_at" TIMESTAMP(3),
    "approved_by" TEXT,
    "exported_at" TIMESTAMP(3),
    "export_path" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "payroll_batches_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payslips" (
    "id" TEXT NOT NULL,
    "batch_id" TEXT NOT NULL,
    "carer_id" TEXT NOT NULL,
    "timesheet_id" TEXT,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "regular_hours" DOUBLE PRECISION NOT NULL,
    "overtime_hours" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_hours" DOUBLE PRECISION NOT NULL,
    "regular_pay" DOUBLE PRECISION NOT NULL,
    "overtime_pay" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "gross_pay" DOUBLE PRECISION NOT NULL,
    "tax_deduction" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "ni_deduction" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "pension_deduction" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "other_deductions" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "total_deductions" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "net_pay" DOUBLE PRECISION NOT NULL,
    "status" "PayslipStatus" NOT NULL DEFAULT 'GENERATED',
    "sent_at" TIMESTAMP(3),
    "viewed_at" TIMESTAMP(3),

    CONSTRAINT "payslips_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "compliance_reports" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "report_type" "ComplianceReportType" NOT NULL,
    "title" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "report_data" JSONB NOT NULL,
    "summary" JSONB,
    "pass_rate" DOUBLE PRECISION,
    "fail_count" INTEGER,
    "warning_count" INTEGER,
    "status" "ReportStatus" NOT NULL DEFAULT 'GENERATING',
    "generated_at" TIMESTAMP(3),
    "generated_by" TEXT,
    "export_path" TEXT,
    "export_format" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "compliance_reports_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "rostering_constraints_tenant_id_name_key" ON "rostering_constraints"("tenant_id", "name");

-- CreateIndex
CREATE UNIQUE INDEX "travel_matrix_cache_from_postcode_to_postcode_mode_key" ON "travel_matrix_cache"("from_postcode", "to_postcode", "mode");

-- CreateIndex
CREATE INDEX "rosters_tenant_id_idx" ON "rosters"("tenant_id");

-- CreateIndex
CREATE INDEX "rosters_start_date_end_date_idx" ON "rosters"("start_date", "end_date");

-- CreateIndex
CREATE INDEX "rosters_status_idx" ON "rosters"("status");

-- CreateIndex
CREATE INDEX "assignments_tenant_id_idx" ON "assignments"("tenant_id");

-- CreateIndex
CREATE INDEX "assignments_carer_id_idx" ON "assignments"("carer_id");

-- CreateIndex
CREATE INDEX "assignments_scheduled_time_idx" ON "assignments"("scheduled_time");

-- CreateIndex
CREATE INDEX "assignments_status_idx" ON "assignments"("status");

-- CreateIndex
CREATE INDEX "assignments_locked_idx" ON "assignments"("locked");

-- CreateIndex
CREATE UNIQUE INDEX "assignments_roster_id_visit_id_key" ON "assignments"("roster_id", "visit_id");

-- CreateIndex
CREATE INDEX "carer_location_updates_carer_id_idx" ON "carer_location_updates"("carer_id");

-- CreateIndex
CREATE INDEX "carer_location_updates_recorded_at_idx" ON "carer_location_updates"("recorded_at");

-- CreateIndex
CREATE INDEX "visit_check_ins_visit_id_idx" ON "visit_check_ins"("visit_id");

-- CreateIndex
CREATE INDEX "visit_check_ins_carer_id_idx" ON "visit_check_ins"("carer_id");

-- CreateIndex
CREATE INDEX "visit_check_ins_check_in_time_idx" ON "visit_check_ins"("check_in_time");

-- CreateIndex
CREATE UNIQUE INDEX "visit_check_ins_visit_id_carer_id_key" ON "visit_check_ins"("visit_id", "carer_id");

-- CreateIndex
CREATE INDEX "visit_check_outs_visit_id_idx" ON "visit_check_outs"("visit_id");

-- CreateIndex
CREATE INDEX "visit_check_outs_carer_id_idx" ON "visit_check_outs"("carer_id");

-- CreateIndex
CREATE INDEX "visit_check_outs_check_out_time_idx" ON "visit_check_outs"("check_out_time");

-- CreateIndex
CREATE UNIQUE INDEX "visit_check_outs_visit_id_carer_id_key" ON "visit_check_outs"("visit_id", "carer_id");

-- CreateIndex
CREATE INDEX "lateness_alerts_tenant_id_idx" ON "lateness_alerts"("tenant_id");

-- CreateIndex
CREATE INDEX "lateness_alerts_visit_id_idx" ON "lateness_alerts"("visit_id");

-- CreateIndex
CREATE INDEX "lateness_alerts_carer_id_idx" ON "lateness_alerts"("carer_id");

-- CreateIndex
CREATE INDEX "lateness_alerts_status_idx" ON "lateness_alerts"("status");

-- CreateIndex
CREATE INDEX "incidents_tenant_id_idx" ON "incidents"("tenant_id");

-- CreateIndex
CREATE INDEX "incidents_visit_id_idx" ON "incidents"("visit_id");

-- CreateIndex
CREATE INDEX "incidents_carer_id_idx" ON "incidents"("carer_id");

-- CreateIndex
CREATE INDEX "incidents_status_idx" ON "incidents"("status");

-- CreateIndex
CREATE INDEX "incidents_severity_idx" ON "incidents"("severity");

-- CreateIndex
CREATE INDEX "assignment_history_assignment_id_idx" ON "assignment_history"("assignment_id");

-- CreateIndex
CREATE INDEX "assignment_history_tenant_id_idx" ON "assignment_history"("tenant_id");

-- CreateIndex
CREATE INDEX "assignment_history_created_at_idx" ON "assignment_history"("created_at");

-- CreateIndex
CREATE INDEX "travel_matrix_expires_at_idx" ON "travel_matrix"("expires_at");

-- CreateIndex
CREATE UNIQUE INDEX "travel_matrix_from_postcode_to_postcode_key" ON "travel_matrix"("from_postcode", "to_postcode");

-- CreateIndex
CREATE INDEX "visit_eligibility_tenant_id_idx" ON "visit_eligibility"("tenant_id");

-- CreateIndex
CREATE INDEX "visit_eligibility_visit_id_idx" ON "visit_eligibility"("visit_id");

-- CreateIndex
CREATE INDEX "visit_eligibility_carer_id_idx" ON "visit_eligibility"("carer_id");

-- CreateIndex
CREATE INDEX "visit_eligibility_eligible_idx" ON "visit_eligibility"("eligible");

-- CreateIndex
CREATE UNIQUE INDEX "visit_eligibility_visit_id_carer_id_key" ON "visit_eligibility"("visit_id", "carer_id");

-- CreateIndex
CREATE INDEX "roster_versions_tenant_id_idx" ON "roster_versions"("tenant_id");

-- CreateIndex
CREATE INDEX "roster_versions_roster_id_idx" ON "roster_versions"("roster_id");

-- CreateIndex
CREATE INDEX "roster_versions_published_at_idx" ON "roster_versions"("published_at");

-- CreateIndex
CREATE INDEX "carer_notification_preferences_tenant_id_idx" ON "carer_notification_preferences"("tenant_id");

-- CreateIndex
CREATE INDEX "carer_notification_preferences_carer_id_idx" ON "carer_notification_preferences"("carer_id");

-- CreateIndex
CREATE UNIQUE INDEX "carer_notification_preferences_tenant_id_carer_id_key" ON "carer_notification_preferences"("tenant_id", "carer_id");

-- CreateIndex
CREATE INDEX "escalation_history_tenant_id_idx" ON "escalation_history"("tenant_id");

-- CreateIndex
CREATE INDEX "escalation_history_original_assignment_id_idx" ON "escalation_history"("original_assignment_id");

-- CreateIndex
CREATE INDEX "escalation_history_escalated_from_idx" ON "escalation_history"("escalated_from");

-- CreateIndex
CREATE INDEX "escalation_history_escalated_to_idx" ON "escalation_history"("escalated_to");

-- CreateIndex
CREATE INDEX "cluster_metrics_tenant_id_idx" ON "cluster_metrics"("tenant_id");

-- CreateIndex
CREATE INDEX "cluster_metrics_cluster_id_idx" ON "cluster_metrics"("cluster_id");

-- CreateIndex
CREATE UNIQUE INDEX "cluster_metrics_cluster_id_calculated_at_key" ON "cluster_metrics"("cluster_id", "calculated_at");

-- CreateIndex
CREATE INDEX "roster_publications_tenant_id_idx" ON "roster_publications"("tenant_id");

-- CreateIndex
CREATE INDEX "roster_publications_roster_id_idx" ON "roster_publications"("roster_id");

-- CreateIndex
CREATE INDEX "roster_publications_published_at_idx" ON "roster_publications"("published_at");

-- CreateIndex
CREATE INDEX "roster_publications_status_idx" ON "roster_publications"("status");

-- CreateIndex
CREATE INDEX "published_assignments_carer_id_idx" ON "published_assignments"("carer_id");

-- CreateIndex
CREATE INDEX "published_assignments_status_idx" ON "published_assignments"("status");

-- CreateIndex
CREATE INDEX "published_assignments_notification_sent_at_idx" ON "published_assignments"("notification_sent_at");

-- CreateIndex
CREATE UNIQUE INDEX "published_assignments_publication_id_assignment_id_key" ON "published_assignments"("publication_id", "assignment_id");

-- CreateIndex
CREATE INDEX "disruptions_tenant_id_idx" ON "disruptions"("tenant_id");

-- CreateIndex
CREATE INDEX "disruptions_status_idx" ON "disruptions"("status");

-- CreateIndex
CREATE INDEX "disruptions_severity_idx" ON "disruptions"("severity");

-- CreateIndex
CREATE INDEX "disruptions_type_idx" ON "disruptions"("type");

-- CreateIndex
CREATE INDEX "disruptions_reported_at_idx" ON "disruptions"("reported_at");

-- CreateIndex
CREATE INDEX "disruption_actions_disruption_id_idx" ON "disruption_actions"("disruption_id");

-- CreateIndex
CREATE INDEX "disruption_actions_performed_at_idx" ON "disruption_actions"("performed_at");

-- CreateIndex
CREATE INDEX "timesheets_tenant_id_idx" ON "timesheets"("tenant_id");

-- CreateIndex
CREATE INDEX "timesheets_carer_id_idx" ON "timesheets"("carer_id");

-- CreateIndex
CREATE INDEX "timesheets_status_idx" ON "timesheets"("status");

-- CreateIndex
CREATE INDEX "timesheets_period_start_period_end_idx" ON "timesheets"("period_start", "period_end");

-- CreateIndex
CREATE UNIQUE INDEX "timesheets_tenant_id_carer_id_period_start_key" ON "timesheets"("tenant_id", "carer_id", "period_start");

-- CreateIndex
CREATE INDEX "timesheet_entries_timesheet_id_idx" ON "timesheet_entries"("timesheet_id");

-- CreateIndex
CREATE INDEX "timesheet_entries_visit_id_idx" ON "timesheet_entries"("visit_id");

-- CreateIndex
CREATE INDEX "timesheet_exceptions_timesheet_id_idx" ON "timesheet_exceptions"("timesheet_id");

-- CreateIndex
CREATE INDEX "timesheet_exceptions_status_idx" ON "timesheet_exceptions"("status");

-- CreateIndex
CREATE INDEX "timesheet_exceptions_type_idx" ON "timesheet_exceptions"("type");

-- CreateIndex
CREATE INDEX "timesheet_adjustments_timesheet_id_idx" ON "timesheet_adjustments"("timesheet_id");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_invoice_number_key" ON "invoices"("invoice_number");

-- CreateIndex
CREATE INDEX "invoices_tenant_id_idx" ON "invoices"("tenant_id");

-- CreateIndex
CREATE INDEX "invoices_client_id_idx" ON "invoices"("client_id");

-- CreateIndex
CREATE INDEX "invoices_status_idx" ON "invoices"("status");

-- CreateIndex
CREATE INDEX "invoices_invoice_date_idx" ON "invoices"("invoice_date");

-- CreateIndex
CREATE INDEX "invoices_due_date_idx" ON "invoices"("due_date");

-- CreateIndex
CREATE INDEX "invoice_line_items_invoice_id_idx" ON "invoice_line_items"("invoice_id");

-- CreateIndex
CREATE INDEX "invoice_line_items_visit_id_idx" ON "invoice_line_items"("visit_id");

-- CreateIndex
CREATE INDEX "invoice_payments_invoice_id_idx" ON "invoice_payments"("invoice_id");

-- CreateIndex
CREATE UNIQUE INDEX "payroll_batches_batch_number_key" ON "payroll_batches"("batch_number");

-- CreateIndex
CREATE INDEX "payroll_batches_tenant_id_idx" ON "payroll_batches"("tenant_id");

-- CreateIndex
CREATE INDEX "payroll_batches_status_idx" ON "payroll_batches"("status");

-- CreateIndex
CREATE INDEX "payroll_batches_period_start_period_end_idx" ON "payroll_batches"("period_start", "period_end");

-- CreateIndex
CREATE INDEX "payslips_batch_id_idx" ON "payslips"("batch_id");

-- CreateIndex
CREATE INDEX "payslips_carer_id_idx" ON "payslips"("carer_id");

-- CreateIndex
CREATE INDEX "payslips_status_idx" ON "payslips"("status");

-- CreateIndex
CREATE INDEX "compliance_reports_tenant_id_idx" ON "compliance_reports"("tenant_id");

-- CreateIndex
CREATE INDEX "compliance_reports_report_type_idx" ON "compliance_reports"("report_type");

-- CreateIndex
CREATE INDEX "compliance_reports_period_start_period_end_idx" ON "compliance_reports"("period_start", "period_end");

-- AddForeignKey
ALTER TABLE "request_carer_matches" ADD CONSTRAINT "request_carer_matches_carerId_fkey" FOREIGN KEY ("carerId") REFERENCES "carers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assignments" ADD CONSTRAINT "assignments_roster_id_fkey" FOREIGN KEY ("roster_id") REFERENCES "rosters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assignments" ADD CONSTRAINT "assignments_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "external_requests"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assignments" ADD CONSTRAINT "assignments_carer_id_fkey" FOREIGN KEY ("carer_id") REFERENCES "carers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "roster_publications" ADD CONSTRAINT "roster_publications_roster_id_fkey" FOREIGN KEY ("roster_id") REFERENCES "rosters"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published_assignments" ADD CONSTRAINT "published_assignments_publication_id_fkey" FOREIGN KEY ("publication_id") REFERENCES "roster_publications"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published_assignments" ADD CONSTRAINT "published_assignments_assignment_id_fkey" FOREIGN KEY ("assignment_id") REFERENCES "assignments"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published_assignments" ADD CONSTRAINT "published_assignments_carer_id_fkey" FOREIGN KEY ("carer_id") REFERENCES "carers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "disruption_actions" ADD CONSTRAINT "disruption_actions_disruption_id_fkey" FOREIGN KEY ("disruption_id") REFERENCES "disruptions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheets" ADD CONSTRAINT "timesheets_carer_id_fkey" FOREIGN KEY ("carer_id") REFERENCES "carers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheet_entries" ADD CONSTRAINT "timesheet_entries_timesheet_id_fkey" FOREIGN KEY ("timesheet_id") REFERENCES "timesheets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheet_entries" ADD CONSTRAINT "timesheet_entries_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "external_requests"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheet_exceptions" ADD CONSTRAINT "timesheet_exceptions_timesheet_id_fkey" FOREIGN KEY ("timesheet_id") REFERENCES "timesheets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "timesheet_adjustments" ADD CONSTRAINT "timesheet_adjustments_timesheet_id_fkey" FOREIGN KEY ("timesheet_id") REFERENCES "timesheets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_line_items" ADD CONSTRAINT "invoice_line_items_invoice_id_fkey" FOREIGN KEY ("invoice_id") REFERENCES "invoices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_line_items" ADD CONSTRAINT "invoice_line_items_visit_id_fkey" FOREIGN KEY ("visit_id") REFERENCES "external_requests"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_payments" ADD CONSTRAINT "invoice_payments_invoice_id_fkey" FOREIGN KEY ("invoice_id") REFERENCES "invoices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "payslips" ADD CONSTRAINT "payslips_batch_id_fkey" FOREIGN KEY ("batch_id") REFERENCES "payroll_batches"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "payslips" ADD CONSTRAINT "payslips_carer_id_fkey" FOREIGN KEY ("carer_id") REFERENCES "carers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "payslips" ADD CONSTRAINT "payslips_timesheet_id_fkey" FOREIGN KEY ("timesheet_id") REFERENCES "timesheets"("id") ON DELETE SET NULL ON UPDATE CASCADE;
