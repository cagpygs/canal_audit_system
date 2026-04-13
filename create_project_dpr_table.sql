CREATE TABLE IF NOT EXISTS project_dpr (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    module VARCHAR(128) NOT NULL DEFAULT 'contract_management',
    project_name TEXT NOT NULL,
    project_key TEXT NOT NULL,
    dpr_form_data TEXT,
    category_of_project TEXT,
    type_of_project TEXT,
    location_of_head_works TEXT,
    date_of_investement_clearance_by_goi TEXT,
    date_of_cwc_clearence TEXT,
    date_of_approval_of_efc TEXT,
    districts_covered TEXT,
    gross_command_area TEXT,
    cca TEXT,
    irrigation_potential_in_rabi TEXT,
    irrigation_potential_in_kharif TEXT,
    requirement_of_water_for_project TEXT,
    availability_of_water_against_the_requirement TEXT,
    pre_project_crop_pattern_in_rabi TEXT,
    pre_project_crop_pattern_in_kharif TEXT,
    post_project_crop_pattern_in_rabi TEXT,
    post_project_crop_pattern_in_kharif TEXT,
    dpr_file_name TEXT,
    dpr_file_path TEXT,
    upload_complete_dpr_file_name TEXT,
    upload_complete_dpr_file_path TEXT,
    investment_clearence_file_name TEXT,
    investment_clearence_file_path TEXT,
    cwc_clearence_file_name TEXT,
    cwc_clearence_file_path TEXT,
    dpr_approval_by_efc_file_name TEXT,
    dpr_approval_by_efc_file_path TEXT,
    survey_reports_file_name TEXT,
    survey_reports_file_path TEXT,
    date_of_approval_revised_dpr_revision_1 TEXT,
    amount_of_revised_dpr_revision_1 TEXT,
    target_date_to_complete_project_revision_1 TEXT,
    date_of_approval_revised_dpr_revision_2 TEXT,
    amount_of_revised_dpr_revision_2 TEXT,
    target_date_to_complete_project_revision_2 TEXT,
    date_of_approval_revised_dpr_revision_3 TEXT,
    amount_of_revised_dpr_revision_3 TEXT,
    target_date_to_complete_project_revision_3 TEXT,
    date_of_approval_revised_dpr_revision_4 TEXT,
    amount_of_revised_dpr_revision_4 TEXT,
    target_date_to_complete_project_revision_4 TEXT,
    date_of_approval_revised_dpr_revision_5 TEXT,
    amount_of_revised_dpr_revision_5 TEXT,
    target_date_to_complete_project_revision_5 TEXT,
    date_of_approval_revised_dpr_revision_6 TEXT,
    amount_of_revised_dpr_revision_6 TEXT,
    target_date_to_complete_project_revision_6 TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, module, project_key)
);

CREATE INDEX IF NOT EXISTS idx_project_dpr_user_module
ON project_dpr (user_id, module);

-- Cleanup legacy dummy columns from older versions.
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummmy_field_1;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummmy_field_2;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummmy_field_3;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummmy_field_4;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummmy_field_5;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummy_field_1;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummy_field_2;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummy_field_3;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummy_field_4;
ALTER TABLE IF EXISTS project_dpr DROP COLUMN IF EXISTS dummy_field_5;
