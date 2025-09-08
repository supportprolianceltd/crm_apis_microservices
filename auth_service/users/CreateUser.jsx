import React, { useState, useEffect } from "react";
import "./CreateUser.css";

const initialState = {
  email: "",
  password: "",
  first_name: "",
  last_name: "",
  role: "carer",
  job_role: "",
  has_accepted_terms: false,
  profile: {
    work_phone: "",
    personal_phone: "",
    gender: "",
    dob: "",
    street: "",
    city: "",
    state: "",
    zip_code: "",
    department: "",
    marital_status: "",
    profile_image: null,
    is_driver: false,
    type_of_vehicle: "",
    drivers_licence_image1: null,
    drivers_licence_image2: null,
    drivers_licence_country_of_issue: "",
    drivers_licence_date_issue: "",
    drivers_licence_expiry_date: "",
    drivers_license_insurance_provider: "",
    drivers_licence_insurance_expiry_date: "",
    drivers_licence_issuing_authority: "",
    drivers_licence_policy_number: "",
    assessor_name: "",
    manual_handling_risk: "",
    lone_working_risk: "",
    infection_risk: "",
    next_of_kin: "",
    next_of_kin_address: "",
    next_of_kin_phone_number: "",
    next_of_kin_alternate_phone: "",
    relationship_to_next_of_kin: "",
    next_of_kin_email: "",
    next_of_kin_town: "",
    next_of_kin_zip_code: "",
    Right_to_Work_status: "",
    Right_to_Work_passport_holder: "",
    Right_to_Work_document_type: "",
    Right_to_Work_share_code: "",
    Right_to_Work_document_number: "",
    Right_to_Work_document_expiry_date: "",
    Right_to_Work_country_of_issue: "",
    Right_to_Work_file: null,
    Right_to_Work_restrictions: "",
    dbs_type: "",
    dbs_certificate: null,
    dbs_certificate_number: "",
    dbs_issue_date: "",
    dbs_update_file: null,
    dbs_update_certificate_number: "",
    dbs_update_issue_date: "",
    dbs_status_check: false,
    bank_name: "",
    account_number: "",
    account_name: "",
    account_type: "",
    access_duration: "",
    system_access_rostering: false,
    system_access_hr: false,
    system_access_recruitment: false,
    system_access_training: false,
    system_access_finance: false,
    system_access_compliance: false,
    system_access_co_superadmin: false,
    system_access_asset_management: false,
    vehicle_type: "",
  },
  professional_qualifications: [],
  employment_details: [],
  education_details: [],
  reference_checks: [],
  proof_of_address: [],
  insurance_verifications: [],
  driving_risk_assessments: [],
  legal_work_eligibilities: [],
  other_user_documents: [],
};

export default function CreateUser() {
  const [form, setForm] = useState(() => {
    const savedForm = localStorage.getItem("createUserForm");
    try {
      const parsedForm = savedForm ? JSON.parse(savedForm) : initialState;
      return { ...initialState, ...parsedForm, profile: { ...initialState.profile, ...parsedForm.profile } };
    } catch (error) {
      console.error("Error parsing saved form data:", error);
      return initialState;
    }
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const token = localStorage.getItem("accessToken");

  useEffect(() => {
    localStorage.setItem("createUserForm", JSON.stringify(form));
  }, [form]);

  function handleChange(e, section = null, field = null) {
    const { name, value, type, checked, files } = e.target;
    if (section) {
      setForm((prev) => ({
        ...prev,
        [section]: {
          ...prev[section],
          [field || name]: type === "checkbox" ? checked : files ? files[0] : value,
        },
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        [name]: type === "checkbox" ? checked : files ? files[0] : value,
      }));
    }
  }

  function handleArrayChange(e, arrName, idx, field) {
    const arr = [...form[arrName]];
    const { value, type, checked, files } = e.target;
    arr[idx][field] = type === "checkbox" ? checked : files ? files[0] : value;
    setForm((prev) => ({ ...prev, [arrName]: arr }));
  }

  function addArrayItem(arrName, obj) {
    setForm((prev) => ({
      ...prev,
      [arrName]: [...prev[arrName], obj],
    }));
  }

  function removeArrayItem(arrName, idx) {
    setForm((prev) => ({
      ...prev,
      [arrName]: prev[arrName].filter((_, i) => i !== idx),
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    for (const q of form.professional_qualifications) {
      if (!q.name || q.name.trim() === "") {
        setMessage("Please fill in all required fields for professional qualifications.");
        setLoading(false);
        return;
      }
    }

    try {
      const formData = new FormData();

      // Add simple fields
      Object.entries(form).forEach(([key, value]) => {
        if (
          [
            "professional_qualifications",
            "employment_details",
            "education_details",
            "reference_checks",
            "proof_of_address",
            "insurance_verifications",
            "driving_risk_assessments",
            "legal_work_eligibilities",
            "other_user_documents",
            "profile",
          ].includes(key)
        ) {
          return;
        }
        formData.append(key, value);
      });

      // Add profile fields
      Object.entries(form.profile).forEach(([key, value]) => {
        if (value instanceof File) {
          formData.append(`profile.${key}`, value);
        } else {
          formData.append(`profile.${key}`, value || "");
        }
      });

      // Add array fields as JSON
      const arrayFields = [
        "professional_qualifications",
        "employment_details",
        "education_details",
        "reference_checks",
        "proof_of_address",
        "insurance_verifications",
        "driving_risk_assessments",
        "legal_work_eligibilities",
        "other_user_documents",
      ];
      arrayFields.forEach((arrName) => {
        // For professional_qualifications, remove image_file before JSON.stringify
        if (arrName === "professional_qualifications") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { image_file, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.image_file instanceof File) {
              formData.append(`professional_qualification_image_file_${idx}`, item.image_file);
            }
          });
        } else if (arrName === "education_details") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { certificate, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.certificate instanceof File) {
              formData.append(`education_certificate_${idx}`, item.certificate);
            }
          });
        } else if (arrName === "proof_of_address") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { document, nin_document, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.document instanceof File) {
              formData.append(`proof_of_address_document_${idx}`, item.document);
            }
            if (item.nin_document instanceof File) {
              formData.append(`proof_of_address_nin_document_${idx}`, item.nin_document);
            }
          });
        } else if (arrName === "insurance_verifications") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { document, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.document instanceof File) {
              formData.append(`insurance_verification_document_${idx}`, item.document);
            }
          });
        } else if (arrName === "driving_risk_assessments") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { supporting_document, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.supporting_document instanceof File) {
              formData.append(`driving_risk_assessment_supporting_document_${idx}`, item.supporting_document);
            }
          });
        } else if (arrName === "legal_work_eligibilities") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { document, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.document instanceof File) {
              formData.append(`legal_work_eligibility_document_${idx}`, item.document);
            }
          });
        } else if (arrName === "other_user_documents") {
          formData.append(
            arrName,
            JSON.stringify(
              form[arrName].map((item) => {
                const { file, ...rest } = item;
                return rest;
              })
            )
          );
          form[arrName].forEach((item, idx) => {
            if (item.file instanceof File) {
              formData.append(`other_user_document_file_${idx}`, item.file);
            }
          });
        } else {
          formData.append(arrName, JSON.stringify(form[arrName]));
        }
      });

      const res = await fetch("http://localhost:9090/api/user/users/", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (res.ok) {
        setMessage("User created successfully!");
        setForm(initialState);
        localStorage.removeItem("createUserForm");
      } else {
        const errorData = await res.json();
        setMessage(`Error: ${errorData.message || "Failed to create user."}`);
      }
    } catch (err) {
      setMessage("Network error.");
    }
    setLoading(false);
  }

  return (
    <div className="create-user-container">
      <h2>Create User</h2>
      <form onSubmit={handleSubmit} encType="multipart/form-data">
        <h3>Basic Info</h3>
        <input name="email" value={form.email} onChange={handleChange} placeholder="Email" required />
        <input name="password" type="password" value={form.password} onChange={handleChange} placeholder="Password" required />
        <input name="first_name" value={form.first_name} onChange={handleChange} placeholder="First Name" />
        <input name="last_name" value={form.last_name} onChange={handleChange} placeholder="Last Name" />
        <select name="role" value={form.role} onChange={handleChange}>
          <option value="carer">Carer</option>
          <option value="admin">Admin</option>
          <option value="co-admin">Co-Admin</option>
          <option value="hr">HR</option>
          <option value="client">Client</option>
          <option value="family">Family</option>
          <option value="auditor">Auditor</option>
          <option value="tutor">Tutor</option>
          <option value="assessor">Assessor</option>
          <option value="iqa">IQA</option>
          <option value="eqa">EQA</option>
          <option value="recruiter">Recruiter</option>
          <option value="team_manager">Team Manager</option>
        </select>
        <input name="job_role" value={form.job_role} onChange={handleChange} placeholder="Job Role" />
        <label>
          Accepted Terms:
          <input type="checkbox" name="has_accepted_terms" checked={form.has_accepted_terms} onChange={handleChange} />
        </label>

        <h3>Profile</h3>
        <input name="work_phone" value={form.profile.work_phone} onChange={(e) => handleChange(e, "profile")} placeholder="Work Phone" />
        <input name="personal_phone" value={form.profile.personal_phone} onChange={(e) => handleChange(e, "profile")} placeholder="Personal Phone" />
        <input name="gender" value={form.profile.gender} onChange={(e) => handleChange(e, "profile")} placeholder="Gender" />
        <input name="dob" type="date" value={form.profile.dob} onChange={(e) => handleChange(e, "profile")} placeholder="DOB" />
        <input name="street" value={form.profile.street} onChange={(e) => handleChange(e, "profile")} placeholder="Street" />
        <input name="city" value={form.profile.city} onChange={(e) => handleChange(e, "profile")} placeholder="City" />
        <input name="state" value={form.profile.state} onChange={(e) => handleChange(e, "profile")} placeholder="State" />
        <input name="zip_code" value={form.profile.zip_code} onChange={(e) => handleChange(e, "profile")} placeholder="Zip Code" />
        <input name="department" value={form.profile.department} onChange={(e) => handleChange(e, "profile")} placeholder="Department" />
        <select name="marital_status" value={form.profile.marital_status} onChange={(e) => handleChange(e, "profile")}>
          <option value="">Select</option>
          <option value="Single">Single</option>
          <option value="Married">Married</option>
          <option value="Divorced">Divorced</option>
          <option value="Widowed">Widowed</option>
          <option value="Others">Others</option>
        </select>
        <label>
          Profile Image:
          <input type="file" onChange={(e) => handleChange(e, "profile", "profile_image")} />
        </label>
        {/* Add more profile fields and file uploads as needed */}

        <h3>Professional Qualifications</h3>
        {form.professional_qualifications.map((q, idx) => (
          <div key={idx}>
            <input
              value={q.name}
              onChange={(e) => handleArrayChange(e, "professional_qualifications", idx, "name")}
              placeholder="Qualification Name"
              required
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleArrayChange(e, "professional_qualifications", idx, "image_file")}
            />
            {q.image_file && <span>{q.image_file.name || "Uploaded File"}</span>}
            <button type="button" onClick={() => removeArrayItem("professional_qualifications", idx)}>
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            addArrayItem("professional_qualifications", { name: "", image_file: "" })
          }
        >
          Add Qualification
        </button>

        <h3>Employment Details</h3>
        {form.employment_details.map((emp, idx) => (
          <div key={idx}>
            <input value={emp.job_role || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "job_role")} placeholder="Job Role" />
            <input value={emp.hierarchy || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "hierarchy")} placeholder="Hierarchy" />
            <input value={emp.department || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "department")} placeholder="Department" />
            <input value={emp.work_email || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "work_email")} placeholder="Work Email" />
            <select value={emp.employment_type || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "employment_type")}>
              <option value="">Select Type</option>
              <option value="Full Time">Full Time</option>
              <option value="Part Time">Part Time</option>
              <option value="Contract">Contract</option>
            </select>
            <input type="date" value={emp.employment_start_date || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "employment_start_date")} placeholder="Start Date" />
            <input type="date" value={emp.employment_end_date || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "employment_end_date")} placeholder="End Date" />
            <input type="date" value={emp.probation_end_date || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "probation_end_date")} placeholder="Probation End Date" />
            <input value={emp.line_manager || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "line_manager")} placeholder="Line Manager" />
            <input value={emp.currency || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "currency")} placeholder="Currency" />
            <input value={emp.salary || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "salary")} placeholder="Salary" />
            <input value={emp.working_days || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "working_days")} placeholder="Working Days" />
            <input value={emp.maximum_working_hours || ""} onChange={(e) => handleArrayChange(e, "employment_details", idx, "maximum_working_hours")} placeholder="Max Working Hours" />
            <button type="button" onClick={() => removeArrayItem("employment_details", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("employment_details", {
          job_role: "", hierarchy: "", department: "", work_email: "", employment_type: "", employment_start_date: "", employment_end_date: "", probation_end_date: "", line_manager: "", currency: "", salary: "", working_days: "", maximum_working_hours: ""
        })}>Add Employment</button>

        <h3>Education Details</h3>
        {form.education_details.map((edu, idx) => (
          <div key={idx}>
            <input
              value={edu.institution || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "institution")}
              placeholder="Institution"
              required
            />
            <input
              value={edu.highest_qualification || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "highest_qualification")}
              placeholder="Highest Qualification"
              required
            />
            <input
              value={edu.course_of_study || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "course_of_study")}
              placeholder="Course of Study"
              required
            />
            <input
              type="number"
              value={edu.start_year || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "start_year")}
              placeholder="Start Year"
              required
            />
            <input
              type="number"
              value={edu.end_year || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "end_year")}
              placeholder="End Year"
              required
            />
            <input
              value={edu.skills || ""}
              onChange={(e) => handleArrayChange(e, "education_details", idx, "skills")}
              placeholder="Skills"
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleArrayChange(e, "education_details", idx, "certificate")}
            />
            {edu.certificate && <span>{edu.certificate.name || "Uploaded File"}</span>}
            <button type="button" onClick={() => removeArrayItem("education_details", idx)}>
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            addArrayItem("education_details", {
              institution: "",
              highest_qualification: "",
              course_of_study: "",
              start_year: "",
              end_year: "",
              certificate: "",
              skills: "",
            })
          }
        >
          Add Education
        </button>

        <h3>Reference Checks</h3>
        {form.reference_checks.map((ref, idx) => (
          <div key={idx}>
            <input
              value={ref.name || ""}
              onChange={(e) => handleArrayChange(e, "reference_checks", idx, "name")}
              placeholder="Name"
              required
            />
            <input
              value={ref.phone_number || ""}
              onChange={(e) => handleArrayChange(e, "reference_checks", idx, "phone_number")}
              placeholder="Phone Number"
              required
            />
            <input
              value={ref.email || ""}
              onChange={(e) => handleArrayChange(e, "reference_checks", idx, "email")}
              placeholder="Email"
              required
            />
            <input
              value={ref.relationship_to_applicant || ""}
              onChange={(e) => handleArrayChange(e, "reference_checks", idx, "relationship_to_applicant")}
              placeholder="Relationship to Applicant"
              required
            />
            <button type="button" onClick={() => removeArrayItem("reference_checks", idx)}>
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            addArrayItem("reference_checks", {
              name: "",
              phone_number: "",
              email: "",
              relationship_to_applicant: "",
            })
          }
        >
          Add Reference
        </button>

        {/* Repeat similar sections for proof_of_address, insurance_verifications, driving_risk_assessments, legal_work_eligibilities, other_user_documents */}
        <h3>Proof Of Address</h3>
        {form.proof_of_address.map((p, idx) => (
          <div key={idx}>
            <select value={p.type || ""} onChange={(e) => handleArrayChange(e, "proof_of_address", idx, "type")}>
              <option value="">Select Type</option>
              <option value="utility_bill">Utility Bill</option>
              <option value="bank_statement">Bank Statement</option>
              <option value="tenancy_agreement">Tenancy Agreement</option>
            </select>
            <input type="date" value={p.issue_date || ""} onChange={(e) => handleArrayChange(e, "proof_of_address", idx, "issue_date")} placeholder="Issue Date" />
            <input value={p.nin || ""} onChange={(e) => handleArrayChange(e, "proof_of_address", idx, "nin")} placeholder="NIN" />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "proof_of_address", idx, "document")} />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "proof_of_address_nin", idx, "nin_document")} />
            <button type="button" onClick={() => removeArrayItem("proof_of_address", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("proof_of_address", { type: "", issue_date: "", nin: "", document: "", nin_document: "" })}>Add Proof Of Address</button>

        <h3>Insurance Verification</h3>
        {form.insurance_verifications.map((ins, idx) => (
          <div key={idx}>
            <select value={ins.insurance_type || ""} onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "insurance_type")}>
              <option value="">Select Type</option>
              <option value="public_liability">Public Liability</option>
              <option value="professional_indemnity">Professional Indemnity</option>
            </select>
            <input value={ins.provider_name || ""} onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "provider_name")} placeholder="Provider Name" />
            <input type="date" value={ins.coverage_start_date || ""} onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "coverage_start_date")} placeholder="Coverage Start Date" />
            <input type="date" value={ins.expiry_date || ""} onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "expiry_date")} placeholder="Expiry Date" />
            <input value={ins.phone_number || ""} onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "phone_number")} placeholder="Phone Number" />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "insurance_verifications", idx, "document")} />
            <button type="button" onClick={() => removeArrayItem("insurance_verifications", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("insurance_verifications", { insurance_type: "", provider_name: "", coverage_start_date: "", expiry_date: "", phone_number: "", document: "" })}>Add Insurance</button>

        <h3>Driving Risk Assessment</h3>
        {form.driving_risk_assessments.map((d, idx) => (
          <div key={idx}>
            <input type="date" value={d.assessment_date || ""} onChange={(e) => handleArrayChange(e, "driving_risk_assessments", idx, "assessment_date")} placeholder="Assessment Date" />
            <label>
              Fuel Card Usage Compliance:
              <input type="checkbox" checked={!!d.fuel_card_usage_compliance} onChange={(e) => handleArrayChange({ target: { name: "fuel_card_usage_compliance", type: "checkbox", checked: e.target.checked } }, "driving_risk_assessments", idx, "fuel_card_usage_compliance")} />
            </label>
            <label>
              Road Traffic Compliance:
              <input type="checkbox" checked={!!d.road_traffic_compliance} onChange={(e) => handleArrayChange({ target: { name: "road_traffic_compliance", type: "checkbox", checked: e.target.checked } }, "driving_risk_assessments", idx, "road_traffic_compliance")} />
            </label>
            <label>
              Tracker Usage Compliance:
              <input type="checkbox" checked={!!d.tracker_usage_compliance} onChange={(e) => handleArrayChange({ target: { name: "tracker_usage_compliance", type: "checkbox", checked: e.target.checked } }, "driving_risk_assessments", idx, "tracker_usage_compliance")} />
            </label>
            <label>
              Maintenance Schedule Compliance:
              <input type="checkbox" checked={!!d.maintenance_schedule_compliance} onChange={(e) => handleArrayChange({ target: { name: "maintenance_schedule_compliance", type: "checkbox", checked: e.target.checked } }, "driving_risk_assessments", idx, "maintenance_schedule_compliance")} />
            </label>
            <textarea value={d.additional_notes || ""} onChange={(e) => handleArrayChange(e, "driving_risk_assessments", idx, "additional_notes")} placeholder="Additional Notes" />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "driving_risk_assessments", idx, "supporting_document")} />
            <button type="button" onClick={() => removeArrayItem("driving_risk_assessments", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("driving_risk_assessments", { assessment_date: "", fuel_card_usage_compliance: false, road_traffic_compliance: false, tracker_usage_compliance: false, maintenance_schedule_compliance: false, additional_notes: "", supporting_document: "" })}>Add Driving Risk Assessment</button>

        <h3>Legal Work Eligibility</h3>
        {form.legal_work_eligibilities.map((l, idx) => (
          <div key={idx}>
            <label>
              Evidence of Right to Rent:
              <input type="checkbox" checked={!!l.evidence_of_right_to_rent} onChange={(e) => handleArrayChange({ target: { name: "evidence_of_right_to_rent", type: "checkbox", checked: e.target.checked } }, "legal_work_eligibilities", idx, "evidence_of_right_to_rent")} />
            </label>
            <input type="date" value={l.expiry_date || ""} onChange={(e) => handleArrayChange(e, "legal_work_eligibilities", idx, "expiry_date")} placeholder="Expiry Date" />
            <input value={l.phone_number || ""} onChange={(e) => handleArrayChange(e, "legal_work_eligibilities", idx, "phone_number")} placeholder="Phone Number" />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "legal_work_eligibilities", idx, "document")} />
            <button type="button" onClick={() => removeArrayItem("legal_work_eligibilities", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("legal_work_eligibilities", { evidence_of_right_to_rent: false, expiry_date: "", phone_number: "", document: "" })}>Add Legal Work Eligibility</button>

        <h3>Other User Documents</h3>
        {form.other_user_documents.map((o, idx) => (
          <div key={idx}>
            <input value={o.government_id_type || ""} onChange={(e) => handleArrayChange(e, "other_user_documents", idx, "government_id_type")} placeholder="Government ID Type" />
            <input value={o.document_number || ""} onChange={(e) => handleArrayChange(e, "other_user_documents", idx, "document_number")} placeholder="Document Number" />
            <input type="date" value={o.expiry_date || ""} onChange={(e) => handleArrayChange(e, "other_user_documents", idx, "expiry_date")} placeholder="Expiry Date" />
            <input type="file" accept="image/*" onChange={(e) => handleArrayChange(e, "other_user_documents", idx, "file")} />
            <button type="button" onClick={() => removeArrayItem("other_user_documents", idx)}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => addArrayItem("other_user_documents", { government_id_type: "", document_number: "", expiry_date: "", file: "" })}>Add Other Document</button>

        <button type="submit" disabled={loading}>
          {loading ? "Creating..." : "Create User"}
        </button>
      </form>
      {message && <p>{message}</p>}
    </div>
  );
}