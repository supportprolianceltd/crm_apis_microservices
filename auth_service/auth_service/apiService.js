import { apiClient } from "../../../../config";
import {
  handleApiError,
  handleApiErrorWithValidation,
} from "../../../../utils/helpers";



export const fetchEmployees = async (pageUrl = null) => {
  try {
    const response = await apiClient.get(pageUrl || "/api/user/users");
    return {
      results: response.data.results,
      count: response.data.count,
      next: response.data.next,
      previous: response.data.previous,
    };
  } catch (error) {
    handleApiError(error);
  }
};

export const fetchUsersNoPagination = async () => {
  try {
    const response = await apiClient.get("/api/user/users-no-pagination/", {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("accessToken")}`,
      },
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
    throw error;
  }
};

export const createEmployee = async (employeeData) => {
  try {
    const response = await apiClient.post("/api/user/users/", employeeData);
    return response.data;
  } catch (error) {
    console.log("Create employee error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const fetchSingleEmployee = async (employeeId) => {
  try {
    const response = await apiClient.get(`/api/user/users/${employeeId}/`);
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};

export const deleteEmployee = async (employeeId) => {
  try {
    const response = await apiClient.delete(`/api/user/users/${employeeId}/`);
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};

export const updateEmployee = async (employeeId, employeeData) => {
  try {
    const formData = new FormData();

    // Helper function to append nested objects (unchanged)
    const appendNestedObject = (obj, prefix = "") => {
      Object.keys(obj).forEach((key) => {
        if (obj[key] !== null && obj[key] !== undefined) {
          const formKey = prefix ? `${prefix}[${key}]` : key;

          if (obj[key] instanceof File) {
            formData.append(formKey, obj[key]);
          } else if (Array.isArray(obj[key])) {
            obj[key].forEach((item, index) => {
              if (typeof item === "object" && !(item instanceof File)) {
                appendNestedObject(item, `${formKey}[${index}]`);
              } else if (item instanceof File) {
                formData.append(`${formKey}[${index}]`, item);
              } else {
                formData.append(`${formKey}[${index}]`, item.toString());
              }
            });
          } else if (
            typeof obj[key] === "object" &&
            !(obj[key] instanceof File)
          ) {
            appendNestedObject(obj[key], formKey);
          } else {
            formData.append(formKey, obj[key].toString());
          }
        }
      });
    };

    appendNestedObject(employeeData);

    const response = await apiClient.patch(
      `/api/user/users/${employeeId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update employee error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const regeneratePassword = async (email) => {
  try {
    const response = await apiClient.post(`/api/user/password/regenerate/`, {
      email,
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};

// Create Employment Details
export const createEmploymentDetails = async (employmentData) => {
  try {
    const response = await apiClient.post(
      "/api/user/employment-details/",
      employmentData
    );
    return response.data;
  } catch (error) {
    console.log("Create employment details error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Update Employment Details
export const updateEmploymentDetails = async (employmentId, employmentData) => {
  try {
    const response = await apiClient.patch(
      `/api/user/employment-details/${employmentId}/`,
      employmentData
    );
    return response.data;
  } catch (error) {
    console.log("Update employment details error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Create Professional Qualifications
export const createProfessionalQualification = async (qualificationData) => {
  try {
    const formData = new FormData();
    formData.append("user_id", qualificationData.user_id);
    formData.append("name", qualificationData.name);
    if (qualificationData.image_file) {
      formData.append("image_file", qualificationData.image_file);
    }

    const response = await apiClient.post(
      "/api/user/professional-qualifications/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log(
      "Create professional qualification error:",
      error.response?.data
    );
    handleApiErrorWithValidation(error);
  }
};

// Update Professional Qualifications
export const updateProfessionalQualification = async (
  qualificationId,
  qualificationData
) => {
  try {
    const formData = new FormData();
    formData.append("user_id", qualificationData.user_id);
    formData.append("name", qualificationData.name);
    if (qualificationData.image_file) {
      formData.append("image_file", qualificationData.image_file);
    }

    const response = await apiClient.patch(
      `/api/user/professional-qualifications/${qualificationId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log(
      "Update professional qualification error:",
      error.response?.data
    );
    handleApiErrorWithValidation(error);
  }
};

// Education Details
export const createEducationDetails = async (educationData) => {
  try {
    const formData = new FormData();
    Object.keys(educationData).forEach((key) => {
      if (educationData[key] !== null && educationData[key] !== undefined) {
        if (educationData[key] instanceof File) {
          formData.append(key, educationData[key]);
        } else {
          formData.append(key, educationData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/education-details/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create education details error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateEducationDetails = async (educationId, educationData) => {
  try {
    const formData = new FormData();
    Object.keys(educationData).forEach((key) => {
      if (educationData[key] !== null && educationData[key] !== undefined) {
        if (educationData[key] instanceof File) {
          formData.append(key, educationData[key]);
        } else {
          formData.append(key, educationData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/education-details/${educationId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update education details error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Reference Checks
export const createReferenceChecks = async (referenceData) => {
  try {
    const formData = new FormData();
    Object.keys(referenceData).forEach((key) => {
      if (referenceData[key] !== null && referenceData[key] !== undefined) {
        if (referenceData[key] instanceof File) {
          formData.append(key, referenceData[key]);
        } else {
          formData.append(key, referenceData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/reference-checks/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create reference checks error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateReferenceChecks = async (referenceId, referenceData) => {
  try {
    const formData = new FormData();
    Object.keys(referenceData).forEach((key) => {
      if (referenceData[key] !== null && referenceData[key] !== undefined) {
        if (referenceData[key] instanceof File) {
          formData.append(key, referenceData[key]);
        } else {
          formData.append(key, referenceData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/reference-checks/${referenceId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update reference checks error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Proof of Address
export const createProofOfAddress = async (proofData) => {
  try {
    const formData = new FormData();
    Object.keys(proofData).forEach((key) => {
      if (proofData[key] !== null && proofData[key] !== undefined) {
        if (proofData[key] instanceof File) {
          formData.append(key, proofData[key]);
        } else {
          formData.append(key, proofData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/proof-of-address/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create proof of address error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateProofOfAddress = async (proofId, proofData) => {
  try {
    const formData = new FormData();
    Object.keys(proofData).forEach((key) => {
      if (proofData[key] !== null && proofData[key] !== undefined) {
        if (proofData[key] instanceof File) {
          formData.append(key, proofData[key]);
        } else {
          formData.append(key, proofData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/proof-of-address/${proofId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update proof of address error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Insurance Verifications
export const createInsuranceVerifications = async (insuranceData) => {
  try {
    const formData = new FormData();
    Object.keys(insuranceData).forEach((key) => {
      if (insuranceData[key] !== null && insuranceData[key] !== undefined) {
        if (insuranceData[key] instanceof File) {
          formData.append(key, insuranceData[key]);
        } else {
          formData.append(key, insuranceData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/insurance-verifications/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create insurance verifications error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateInsuranceVerifications = async (
  insuranceId,
  insuranceData
) => {
  try {
    const formData = new FormData();
    Object.keys(insuranceData).forEach((key) => {
      if (insuranceData[key] !== null && insuranceData[key] !== undefined) {
        if (insuranceData[key] instanceof File) {
          formData.append(key, insuranceData[key]);
        } else {
          formData.append(key, insuranceData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/insurance-verifications/${insuranceId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update insurance verifications error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Driving Risk Assessments
export const createDrivingRiskAssessments = async (assessmentData) => {
  try {
    const formData = new FormData();
    Object.keys(assessmentData).forEach((key) => {
      if (assessmentData[key] !== null && assessmentData[key] !== undefined) {
        if (assessmentData[key] instanceof File) {
          formData.append(key, assessmentData[key]);
        } else {
          formData.append(key, assessmentData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/driving-risk-assessments/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create driving risk assessments error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateDrivingRiskAssessments = async (
  assessmentId,
  assessmentData
) => {
  try {
    const formData = new FormData();
    Object.keys(assessmentData).forEach((key) => {
      if (assessmentData[key] !== null && assessmentData[key] !== undefined) {
        if (assessmentData[key] instanceof File) {
          formData.append(key, assessmentData[key]);
        } else {
          formData.append(key, assessmentData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/driving-risk-assessments/${assessmentId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update driving risk assessments error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Legal Work Eligibilities
export const createLegalWorkEligibilities = async (eligibilityData) => {
  try {
    const formData = new FormData();
    Object.keys(eligibilityData).forEach((key) => {
      if (eligibilityData[key] !== null && eligibilityData[key] !== undefined) {
        if (eligibilityData[key] instanceof File) {
          formData.append(key, eligibilityData[key]);
        } else {
          formData.append(key, eligibilityData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/legal-work-eligibilities/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create legal work eligibilities error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateLegalWorkEligibilities = async (
  eligibilityId,
  eligibilityData
) => {
  try {
    const formData = new FormData();
    Object.keys(eligibilityData).forEach((key) => {
      if (eligibilityData[key] !== null && eligibilityData[key] !== undefined) {
        if (eligibilityData[key] instanceof File) {
          formData.append(key, eligibilityData[key]);
        } else {
          formData.append(key, eligibilityData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/legal-work-eligibilities/${eligibilityId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update legal work eligibilities error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Other User Documents
export const createOtherUserDocuments = async (documentData) => {
  try {
    const formData = new FormData();
    Object.keys(documentData).forEach((key) => {
      if (documentData[key] !== null && documentData[key] !== undefined) {
        if (documentData[key] instanceof File) {
          formData.append(key, documentData[key]);
        } else {
          formData.append(key, documentData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/other-user-documents/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create other user documents error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateOtherUserDocuments = async (documentId, documentData) => {
  try {
    const formData = new FormData();
    Object.keys(documentData).forEach((key) => {
      if (documentData[key] !== null && documentData[key] !== undefined) {
        if (documentData[key] instanceof File) {
          formData.append(key, documentData[key]);
        } else {
          formData.append(key, documentData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/other-user-documents/${documentId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update other user documents error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const fetchRosteringRequests = async () => {
  try {
    const response = await apiClient.get("/api/rostering/requests/", {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("accessToken")}`,
      },
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
    throw error;
  }
};

export const autoAssignCarerToCluster = async (payload) => {
  try {
    const response = await apiClient.post("/api/rostering/clusters/auto-assign-carer", payload);
    return response.data;
  } catch (error) {
    console.error("Auto-assign carer to cluster error:", error.response?.data || error);
    // Don't throw, as this is optional and shouldn't block employee creation
  }
};

// Skill Details
export const createSkillDetail = async (skillData) => {
  try {
    const formData = new FormData();
    Object.keys(skillData).forEach((key) => {
      if (skillData[key] !== null && skillData[key] !== undefined) {
        if (skillData[key] instanceof File) {
          formData.append(key, skillData[key]);
        } else {
          formData.append(key, skillData[key].toString());
        }
      }
    });

    const response = await apiClient.post(
      "/api/user/skills/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Create skill detail error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

export const updateSkillDetail = async (skillId, skillData) => {
  try {
    const formData = new FormData();
    Object.keys(skillData).forEach((key) => {
      if (skillData[key] !== null && skillData[key] !== undefined) {
        if (skillData[key] instanceof File) {
          formData.append(key, skillData[key]);
        } else {
          formData.append(key, skillData[key].toString());
        }
      }
    });

    const response = await apiClient.patch(
      `/api/user/skills/${skillId}/`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error) {
    console.log("Update skill detail error:", error.response?.data);
    handleApiErrorWithValidation(error);
  }
};

// Notification API functions
export const fetchInAppMessages = async (params = {}) => {
  try {
    const response = await apiClient.get("/api/notifications/messages/", {
      params,
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};

export const markMessageAsRead = async (messageId) => {
  try {
    const response = await apiClient.patch(
      `/api/notifications/messages/${messageId}/`,
      { read_at: new Date().toISOString() }
    );
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};

export const sendInAppNotification = async (notificationData) => {
  try {
    const response = await apiClient.post("/api/notifications/records/", {
      channel: "inapp",
      ...notificationData,
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
};
