import React, { useState, useEffect, useReducer, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import {
  Save, Cancel, CloudUpload, AddCircle, Delete, Link as LinkIcon,
  PictureAsPdf, VideoLibrary, InsertDriveFile, Edit, Person, People,
  School, Menu as MenuIcon, ArrowBack, Add, Star, CheckCircle
} from '@mui/icons-material';
import { coursesAPI, userAPI } from '../../../../config';
import { DraggableModule } from './ModuleForm';
import LearningPaths from './LearningPaths';
import SCORMxAPISettings from './SCORMxAPISettings';
import CertificateSettings from './CertificateSettings';
import GamificationManager from './GamificationManager';
import InstructorAssignmentDialog from './InstructorAssignmentDialog';
import ErrorBoundary from './ErrorBoundary';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import './CourseForm.css';
import SCORMPlayer from './SCORMPlayer';

const resourceTypes = [
  { value: 'link', label: 'Web Link', icon: <LinkIcon /> },
  { value: 'pdf', label: 'PDF Document', icon: <PictureAsPdf /> },
  { value: 'video', label: 'Video', icon: <VideoLibrary /> },
  { value: 'file', label: 'File', icon: <InsertDriveFile /> }
];

const initialCourseState = {
  id: null,
  title: '',
  code: '',
  description: '',
  category_id: '',
  level: 'Beginner',
  status: 'Draft',
  duration: '',
  is_free: false, // <-- Add this line
  price: 0,
  discount_price: null,
  currency: 'NGN',
  learningOutcomes: [],
  prerequisites: [],
  learningOutcomeInput: '',
  prerequisiteInput: '',
  thumbnail: null,
  thumbnailPreview: null,
  modules: [],
  resources: [],
  instructors: [],
  learningPaths: [],
  certificateSettings: {
    enabled: false,
    template: 'default',
    customText: '',
    signature: null,
    signatureName: '',
    showDate: true,
    showCourseName: true,
    showCompletionHours: true,
    customLogo: null
  },
  scormSettings: {
    enabled: false,
    standard: 'scorm12',
    version: '1.2',
    completionThreshold: 80,
    scoreThreshold: 70,
    tracking: { completion: true, score: true, time: true, progress: true },
    package: null,
    packageName: ''
  }
};

const courseReducer = (state, action) => {
  if (!state) return initialCourseState;
  switch (action.type) {
    case 'UPDATE_FIELD':
      return { ...state, [action.field]: action.value };
    case 'UPDATE_NESTED':
      return { ...state, [action.field]: { ...state[action.field], ...action.value } };
    case 'ADD_ITEM':
      return { ...state, [action.field]: [...state[action.field], action.value] };
    case 'REMOVE_ITEM':
      return { ...state, [action.field]: state[action.field].filter((_, i) => i !== action.index) };
    case 'UPDATE_ITEM':
      return {
        ...state,
        [action.field]: state[action.field].map(item =>
          item.id === action.id ? { ...item, ...action.value } : item
        )
      };
    case 'SET_COURSE':
      return { ...state, ...action.payload };
    case 'RESET':
      return initialCourseState;
    default:
      return state;
  }
};

const tabLabels = [
  { label: 'Details', icon: <Edit fontSize="small" /> },
  { label: 'Modules', icon: <School fontSize="small" /> },
  { label: 'Instructors', icon: <People fontSize="small" /> },
  { label: 'Resources', icon: <InsertDriveFile fontSize="small" /> },
  { label: 'Paths', icon: <LinkIcon fontSize="small" /> },
  { label: 'Certificates', icon: <PictureAsPdf fontSize="small" /> },
  { label: 'SCORM', icon: <VideoLibrary fontSize="small" /> },
  { label: 'Gamification', icon: <Star fontSize="small" /> }
];

const CourseForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = !!id;
  const [course, dispatch] = useReducer(courseReducer, initialCourseState);
  const [categories, setCategories] = useState([]);
  const [activeTab, setActiveTab] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedModules, setSelectedModules] = useState([]);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState('');
  const [loading, setLoading] = useState(false);
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [newCategory, setNewCategory] = useState({ name: '', description: '' });
  const [editingCategory, setEditingCategory] = useState(null);
  const [resourceDialogOpen, setResourceDialogOpen] = useState(false);
  const [currentResource, setCurrentResource] = useState({
    id: null,
    title: '',
    type: 'link',
    url: '',
    file: null
  });
  const [instructorDialogOpen, setInstructorDialogOpen] = useState(false);
  const [scormFile, setScormFile] = useState(null);
  const [scormUploading, setScormUploading] = useState(false);
  const [scormUploadMsg, setScormUploadMsg] = useState('');
  const [learners, setLearners] = useState([]);
  const [selectedLearnerId, setSelectedLearnerId] = useState(null);
  const fileInputRef = useRef();
  const categoryNameInputRef = useRef(null);

  // Fetch categories and course data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [categoriesRes, courseRes] = await Promise.all([
          coursesAPI.getCategories(),
          isEdit ? coursesAPI.getCourse(id) : Promise.resolve(null)
        ]);
        setCategories(categoriesRes.data.results || categoriesRes.data || []);
        if (isEdit && courseRes?.data) {
          dispatch({
            type: 'SET_COURSE',
            payload: {
              ...courseRes.data,
              id: courseRes.data.id || null,
              category_id: courseRes.data.category?.id || courseRes.data.category_id || '',
              description: courseRes.data.description || '',
              learningOutcomes: Array.isArray(courseRes.data.learning_outcomes)
                ? courseRes.data.learning_outcomes.filter(item => typeof item === 'string' && item.trim())
                : [],
              prerequisites: Array.isArray(courseRes.data.prerequisites)
                ? courseRes.data.prerequisites.filter(item => typeof item === 'string' && item.trim())
                : [],
              learningOutcomeInput: '',
              prerequisiteInput: '',
              thumbnail: null,
              thumbnailPreview: courseRes.data.thumbnail?.url || null,
              modules: (courseRes.data.modules || []).map((module, idx) => ({
                ...module,
                order: module.order ?? idx,
                lessons: (module.lessons || []).map((lesson, lessonIdx) => ({
                  ...lesson,
                  order: lesson.order ?? lessonIdx
                }))
              })),
              resources: courseRes.data.resources || [],
              instructors: (courseRes.data.course_instructors || [])
                .filter(i => i.instructor)
                .map(i => ({
                  instructorId: i.instructor.id,
                  name: `${i.instructor.user.first_name} ${i.instructor.user.last_name}`.trim() || i.instructor.user.email,
                  email: i.instructor.user.email,
                  isActive: i.is_active,
                  assignedModules: i.assignment_type === 'all' ? 'all' : (i.modules || []).map(m => m.id)
                }))
            }
          });
        } else if (!isEdit) {
          dispatch({ type: 'SET_COURSE', payload: initialCourseState });
        }
      } catch (error) {
        setApiError('Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id, isEdit]);

  // Fetch only users with role "learners"
  useEffect(() => {
    userAPI.getUsers({ role: 'learners', page_size: 100 }).then(res => {
      setLearners(res.data.results || []);
      if (res.data.results && res.data.results.length > 0) {
        setSelectedLearnerId(res.data.results[0].id); // Default to first learner
      }
    });
  }, []);

  // Responsive sidebar toggle
  const handleSidebarToggle = () => setMobileOpen(!mobileOpen);

  // Form field change handler
  const handleChange = useCallback((field, value) => {
    dispatch({ type: 'UPDATE_FIELD', field, value });
  }, []);

  // Thumbnail upload
  const handleThumbnailChange = (file) => {
    const previewUrl = file ? URL.createObjectURL(file) : course?.thumbnailPreview;
    dispatch({ type: 'UPDATE_FIELD', field: 'thumbnail', value: file });
    dispatch({ type: 'UPDATE_FIELD', field: 'thumbnailPreview', value: previewUrl });
  };

  // Learning Outcomes
  const addLearningOutcome = (outcome) => {
    if (outcome.trim()) {
      dispatch({ type: 'ADD_ITEM', field: 'learningOutcomes', value: outcome.trim() });
      dispatch({ type: 'UPDATE_FIELD', field: 'learningOutcomeInput', value: '' });
    }
  };
  const removeLearningOutcome = (index) => {
    dispatch({ type: 'REMOVE_ITEM', field: 'learningOutcomes', index });
  };

  // Prerequisites
  const addPrerequisite = (prereq) => {
    if (prereq.trim()) {
      dispatch({ type: 'ADD_ITEM', field: 'prerequisites', value: prereq.trim() });
      dispatch({ type: 'UPDATE_FIELD', field: 'prerequisiteInput', value: '' });
    }
  };
  const removePrerequisite = (index) => {
    dispatch({ type: 'REMOVE_ITEM', field: 'prerequisites', index });
  };

  // Module handlers
  const handleModuleChange = (moduleId, updatedModule) => {
    dispatch({ type: 'UPDATE_ITEM', field: 'modules', id: moduleId, value: updatedModule });
  };
  const addModule = async () => {
    setLoading(true);
    try {
      let courseId = id || course?.id;
      if (!isEdit && !courseId) {
        setApiError('Save course details before adding modules.');
        setLoading(false);
        return;
      }
      const existingModulesResponse = await coursesAPI.getModules(courseId);
      const existingModules = existingModulesResponse.data.results || existingModulesResponse.data || [];
      const maxOrder = existingModules.length > 0
        ? Math.max(...existingModules.map(m => m.order)) + 1
        : 0;
      const response = await coursesAPI.createModule(courseId, {
        course: courseId,
        title: 'New Module',
        description: '',
        order: maxOrder,
        is_published: false
      });
      dispatch({
        type: 'ADD_ITEM',
        field: 'modules',
        value: { ...response.data, lessons: [] }
      });
    } catch (error) {
      setApiError('Failed to create module');
    } finally {
      setLoading(false);
    }
  };
  const deleteModule = async (moduleId) => {
    setLoading(true);
    try {
      if (!isNaN(moduleId)) await coursesAPI.deleteModule(id, moduleId);
      const updatedModules = (course?.modules.filter(m => m.id !== moduleId) || []).map((module, idx) => ({
        ...module,
        order: idx
      }));
      await Promise.all(
        updatedModules.map(module =>
          coursesAPI.updateModule(id, module.id, { order: module.order })
        )
      );
      dispatch({ type: 'UPDATE_FIELD', field: 'modules', value: updatedModules });
    } catch (error) {
      setApiError('Failed to delete module');
    } finally {
      setLoading(false);
    }
  };
  const moveModule = (dragIndex, hoverIndex) => {
    const newModules = [...(course?.modules || [])];
    const draggedModule = newModules[dragIndex];
    newModules.splice(dragIndex, 1);
    newModules.splice(hoverIndex, 0, draggedModule);
    dispatch({
      type: 'UPDATE_FIELD',
      field: 'modules',
      value: newModules.map((module, idx) => ({ ...module, order: idx }))
    });
  };

  // Resource handlers
  const saveResource = async (e) => {
    e.preventDefault();
    if (!currentResource.title?.trim()) {
      setApiError('Resource title is required');
      return;
    }
    if (currentResource.type === 'link' && !currentResource.url?.trim()) {
      setApiError('URL is required for web link resources');
      return;
    }
    if (['pdf', 'video', 'file'].includes(currentResource.type) && !currentResource.file && !currentResource.id) {
      setApiError('File is required for this resource type');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('title', currentResource.title);
      formData.append('resource_type', currentResource.type);
      if (currentResource.type === 'link') {
        formData.append('url', currentResource.url || '');
      } else if (currentResource.file) {
        formData.append('file', currentResource.file);
      }
      formData.append('order', course?.resources.length || 0);
      const response = currentResource.id
        ? await coursesAPI.updateResource(id, currentResource.id, formData)
        : await coursesAPI.createResource(id, formData);
      dispatch({
        type: currentResource.id ? 'UPDATE_ITEM' : 'ADD_ITEM',
        field: 'resources',
        id: currentResource.id,
        value: response.data
      });
      setResourceDialogOpen(false);
      setCurrentResource({ id: null, title: '', type: 'link', url: '', file: null });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      setApiError('Failed to save resource');
    } finally {
      setLoading(false);
    }
  };
  const deleteResource = async (resourceId) => {
    setLoading(true);
    try {
      await coursesAPI.deleteResource(id, resourceId);
      dispatch({
        type: 'UPDATE_FIELD',
        field: 'resources',
        value: course?.resources.filter(r => r.id !== resourceId) || []
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      setApiError('Failed to delete resource');
    } finally {
      setLoading(false);
    }
  };

  // Category handlers
  const saveCategory = async (e) => {
    e.preventDefault();
    if (!newCategory.name?.trim()) {
      setErrors({ categoryName: 'Category name is required' });
      return;
    }
    setLoading(true);
    try {
      const payload = {
        name: newCategory.name.trim(),
        description: newCategory.description.trim()
      };
      const response = editingCategory
        ? await coursesAPI.updateCategory(editingCategory.id, payload)
        : await coursesAPI.createCategory(payload);
      setCategories(prev =>
        editingCategory
          ? prev.map(cat => (cat.id === editingCategory.id ? response.data : cat))
          : [...prev, response.data]
      );
      setCategoryDialogOpen(false);
      setNewCategory({ name: '', description: '' });
      setEditingCategory(null);
      setErrors({});
    } catch (error) {
      setApiError('Failed to save category');
    } finally {
      setLoading(false);
    }
  };
  const deleteCategory = async (categoryId) => {
    setLoading(true);
    try {
      await coursesAPI.deleteCategory(categoryId);
      setCategories(prev => prev.filter(cat => cat.id !== categoryId));
    } catch (error) {
      setApiError('Failed to delete category');
    } finally {
      setLoading(false);
    }
  };

  // Instructor handlers
  const handleInstructorAssignment = async (instructor, assignedModules) => {
    if (!course) {
      setApiError('Course data is not loaded. Please try again.');
      return;
    }
    if (!id && !course.id) {
      setApiError('Please save the course before assigning instructors.');
      return;
    }
    const courseId = id || course.id;
    const isAll = !assignedModules || assignedModules === 'all' || assignedModules.length === 0;
    const newInstructor = {
      instructorId: instructor.id,
      name: instructor.name,
      email: instructor.email,
      isActive: true,
      assignedModules: isAll ? 'all' : assignedModules
    };
    setLoading(true);
    try {
      const data = {
        instructor_id: instructor.id,
        assignment_type: isAll ? 'all' : 'specific',
        modules: isAll ? [] : assignedModules,
        is_active: true
      };
      if (course.instructors.some(i => i.instructorId === instructor.id)) {
        await coursesAPI.updateInstructorAssignment(courseId, instructor.id, data);
      } else {
        await coursesAPI.assignInstructor(courseId, data);
      }
      dispatch({
        type: 'UPDATE_FIELD',
        field: 'instructors',
        value: course.instructors.some(i => i.instructorId === instructor.id)
          ? course.instructors.map(i => (i.instructorId === instructor.id ? newInstructor : i))
          : [...course.instructors, newInstructor]
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      setInstructorDialogOpen(false);
    } catch (error) {
      setApiError('Failed to save instructor assignment');
    } finally {
      setLoading(false);
    }
  };
  const handleRemoveInstructor = async (instructorId) => {
    if (!window.confirm('Remove this instructor from the course?')) return;
    try {
      await coursesAPI.deleteInstructorAssignment(course.id, instructorId);
      dispatch({
        type: 'UPDATE_FIELD',
        field: 'course_instructors',
        value: course.course_instructors.filter(
          (ci) => ci.instructor?.id !== instructorId
        ),
      });
    } catch (e) {
      alert('Failed to remove instructor');
    }
  };

  // SCORM handlers
  const handleScormFileChange = (e) => {
    setScormFile(e.target.files[0]);
    setScormUploadMsg('');
  };

  const handleScormUpload = async () => {
    if (!scormFile) {
      setScormUploadMsg('Please select a SCORM .zip file.');
      return;
    }
    setScormUploading(true);
    setScormUploadMsg('');
    const formData = new FormData();
    formData.append('package', scormFile);
    try {
      // Use your scormAPI here, pass course.id or course.id from state
      await scormAPI.uploadPackage(course.id, formData);
      setScormUploadMsg('SCORM package uploaded successfully!');
      setScormFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setScormUploadMsg('Upload failed. Please try again.');
    }
    setScormUploading(false);
  };

  // Validation
  const validateForm = () => {
    const newErrors = {};
    if (!course?.title?.trim()) newErrors.title = 'Title is required';
    if (!course?.code?.trim()) newErrors.code = 'Course code is required';
    if (!course?.description?.trim()) newErrors.description = 'Description is required';
    if (!course?.category_id) newErrors.category = 'Category is required';
    if (course?.learningOutcomes.length === 0) newErrors.learningOutcomes = 'At least one learning outcome is required';
    if (course?.prerequisites.length === 0) newErrors.prerequisites = 'At least one prerequisite is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Save handler
  const handleSave = async (e, redirect = false) => {
    e.preventDefault();
    if (!course) {
      setApiError('Course data is not loaded. Please try again.');
      return;
    }
    if (!validateForm()) return;
    setLoading(true);
    setApiError('');
    try {
      const formData = new FormData();
      const fieldsToInclude = [
        'title', 'code', 'description', 'category_id', 'level', 'status',
        'duration', 'price', 'discount_price', 'currency', 'completion_hours', 'is_free' // <-- Add is_free
      ];
      fieldsToInclude.forEach(key => {
        if (key === 'description') {
          formData.append(key, course.description);
        } else if (key === 'discount_price' && course[key] === null) {
          // Skip null discount_price
        } else if (course[key] !== null && course[key] !== undefined) {
          formData.append(key, course[key]);
        }
      });
      formData.append('learning_outcomes', JSON.stringify(course.learningOutcomes));
      formData.append('prerequisites', JSON.stringify(course.prerequisites));
      if (course.thumbnail instanceof File) {
        formData.append('thumbnail', course.thumbnail);
      }
      const response = isEdit
        ? await coursesAPI.updateCourse(id, formData)
        : await coursesAPI.createCourse(formData);
      if (!isEdit) {
        dispatch({ type: 'SET_COURSE', payload: { ...course, id: response.data.id } });
        navigate(`/admin/courses/edit/${response.data.id}`, { replace: true });
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      if (redirect) navigate('/admin/courses');
    } catch (error) {
      setApiError('Failed to save course');
    } finally {
      setLoading(false);
    }
  };

  // Dialog handlers
  const handleCloseCategoryDialog = () => {
    setCategoryDialogOpen(false);
    setNewCategory({ name: '', description: '' });
    setEditingCategory(null);
    setErrors({});
  };
  const handleCloseInstructorDialog = () => setInstructorDialogOpen(false);

  // Responsive layout
  const isMobile = window.innerWidth <= 900;

  // Add this inside CourseForm component, before return
  const handleFreeChange = (e) => {
    const checked = e.target.checked;
    dispatch({ type: 'UPDATE_FIELD', field: 'is_free', value: checked });
    if (checked) {
      dispatch({ type: 'UPDATE_FIELD', field: 'price', value: null });
      dispatch({ type: 'UPDATE_FIELD', field: 'discount_price', value: null });
    }
  };

  if (!course) {
    return (
      <div className="CourseForm">
        <div className="notification error">
          <span>Error: Course data not loaded. Please try again.</span>
          <button onClick={() => navigate('/admin/courses')}>Back to Courses</button>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className={`CourseForm ${isMobile ? 'mobile' : ''}`}>
        <header className="CourseForm-Header">
          <div className="CourseForm-Header-Grid">
            <h2>
              <Edit className="icon" /> {isEdit ? 'Edit Course' : 'Create New Course'}
            </h2>
            <button className="action-btn" onClick={() => navigate('/admin/courses')}>
              <ArrowBack className="icon" /> Back to Courses
            </button>
          </div>
        </header>
        <main className="CourseForm-Main">
          <aside className={`CourseForm-Sidebar ${mobileOpen ? 'open' : ''}`}>
            <div className="CourseForm-Sidebar-Header">
              <button className="sidebar-toggle" onClick={handleSidebarToggle}>
                <MenuIcon className="icon" />
              </button>
              <h3>Course Sections</h3>
            </div>
            <ul className="sidebar-nav">
              {tabLabels.map((tab, index) => (
                <li
                  key={index}
                  className={`sidebar-item ${activeTab === index ? 'active' : ''} ${tab.disabled ? 'disabled' : ''}`}
                  onClick={() => {
                    if (!tab.disabled) {
                      setActiveTab(index);
                      if (mobileOpen) setMobileOpen(false);
                    }
                  }}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </li>
              ))}
            </ul>
          </aside>
          <section className="CourseForm-Content">
            {apiError && (
              <div className="notification error">
                <span>{apiError}</span>
                <button onClick={() => setApiError('')}>Dismiss</button>
              </div>
            )}
            {saveSuccess && (
              <div className="notification success">
                <CheckCircle className="icon" /> Course saved successfully!
              </div>
            )}
            {loading ? (
              <div className="loading">Loading...</div>
            ) : (
              <form className="CourseForm-Form">
                {activeTab === 0 && (
                  <div className="CourseForm-Grid">
                    <div className="CourseForm-Left">
                      <label className="label">Course Title</label>
                      <input
                        type="text"
                        className="input"
                        value={course.title}
                        onChange={(e) => handleChange('title', e.target.value)}
                        placeholder="Enter course title"
                        aria-describedby="title-error"
                      />
                      {errors.title && <span id="title-error" className="error-text">{errors.title}</span>}

                      <label className="label">Course Code</label>
                      <input
                        type="text"
                        className="input"
                        value={course.code}
                        onChange={(e) => handleChange('code', e.target.value)}
                        placeholder="Enter course code"
                        aria-describedby="code-error"
                      />
                      {errors.code && <span id="code-error" className="error-text">{errors.code}</span>}

                      <label className="label">Description</label>
                      <ErrorBoundary>
                        <ReactQuill
                          value={course.description}
                          onChange={value => handleChange('description', value)}
                          theme="snow"
                          style={{ minHeight: 150, marginBottom: 8 }}
                        />
                      </ErrorBoundary>
                      {errors.description && <span id="description-error" className="error-text">{errors.description}</span>}

                      <div className="section-divider" />

                      <h3>Learning Outcomes</h3>
                      <div className="chip-list">
                        {course.learningOutcomes.map((outcome, index) => (
                          <span key={index} className="chip">
                            {outcome}
                            <Delete className="chip-icon" onClick={() => removeLearningOutcome(index)} />
                          </span>
                        ))}
                      </div>
                      <div className="input-group">
                        <input
                          type="text"
                          className="input"
                          value={course.learningOutcomeInput}
                          onChange={(e) => handleChange('learningOutcomeInput', e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && addLearningOutcome(course.learningOutcomeInput)}
                          placeholder="What will students learn?"
                          aria-describedby="learning-outcomes-error"
                        />
                        <button
                          className="action-btn"
                          type="button"
                          onClick={() => addLearningOutcome(course.learningOutcomeInput)}
                        >
                          <Add className="icon" /> Add
                        </button>
                      </div>
                      {errors.learningOutcomes && (
                        <span id="learning-outcomes-error" className="error-text">{errors.learningOutcomes}</span>
                      )}

                      <div className="section-divider" />

                      <h3>Prerequisites</h3>
                      <div className="chip-list">
                        {course.prerequisites.map((prereq, index) => (
                          <span key={index} className="chip">
                            {prereq}
                            <Delete className="chip-icon" onClick={() => removePrerequisite(index)} />
                          </span>
                        ))}
                      </div>
                      <div className="input-group">
                        <input
                          type="text"
                          className="input"
                          value={course.prerequisiteInput}
                          onChange={(e) => handleChange('prerequisiteInput', e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && addPrerequisite(course.prerequisiteInput)}
                          placeholder="What should students know beforehand?"
                          aria-describedby="prerequisites-error"
                        />
                        <button
                          className="action-btn"
                          type="button"
                          onClick={() => addPrerequisite(course.prerequisiteInput)}
                        >
                          <Add className="icon" /> Add
                        </button>
                      </div>
                      {errors.prerequisites && (
                        <span id="prerequisites-error" className="error-text">{errors.prerequisites}</span>
                      )}
                    </div>
                    <div className="CourseForm-Right">
                      <div className="input-group">
                        <label className="label">Category</label>
                        <select
                          className="select"
                          value={course.category_id || ''}
                          onChange={(e) => handleChange('category_id', e.target.value)}
                          aria-describedby="category-error"
                        >
                          <option value="">Select a category</option>
                          {categories.map(cat => (
                            <option key={cat.id} value={cat.id}>{cat.name}</option>
                          ))}
                        </select>
                        {errors.category && <span id="category-error" className="error-text">{errors.category}</span>}
                        <button
                          className="action-btn"
                          type="button"
                          onClick={() => setCategoryDialogOpen(true)}
                        >
                          <Add className="icon" /> Add Category
                        </button>
                      </div>
                      <ul className="category-list">
                        {categories.map(category => (
                          <li key={category.id} className="category-item">
                            <span>{category.name}</span>
                            <div className="category-actions">
                              <button
                                className="icon-btn"
                                type="button"
                                onClick={() => {
                                  setEditingCategory(category);
                                  setNewCategory({ name: category.name, description: category.description });
                                  setCategoryDialogOpen(true);
                                }}
                              >
                                <Edit className="icon" />
                              </button>
                              <button
                                className="icon-btn danger"
                                type="button"
                                onClick={() => deleteCategory(category.id)}
                              >
                                <Delete className="icon" />
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                      {course.category_id && (
                        <div className="selected-category" style={{ margin: '1rem 0' }}>
                          <span style={{ fontWeight: 500 }}>
                            {categories.find(cat => String(cat.id) === String(course.category_id))?.name}
                          </span>
                          <div className="category-actions" style={{ display: 'inline-flex', gap: 8, marginLeft: 8 }}>
                            <button
                              className="icon-btn"
                              type="button"
                              onClick={() => {
                                const selected = categories.find(cat => String(cat.id) === String(course.category_id));
                                setEditingCategory(selected);
                                setNewCategory({ name: selected.name, description: selected.description });
                                setCategoryDialogOpen(true);
                              }}
                            >
                              <Edit className="icon" />
                            </button>
                            <button
                              className="icon-btn danger"
                              type="button"
                              onClick={() => deleteCategory(course.category_id)}
                            >
                              <Delete className="icon" />
                            </button>
                          </div>
                        </div>
                      )}
                      <label className="label">Level</label>
                      <select
                        className="select"
                        value={course.level}
                        onChange={(e) => handleChange('level', e.target.value)}
                      >
                        <option value="Beginner">Beginner</option>
                        <option value="Intermediate">Intermediate</option>
                        <option value="Advanced">Advanced</option>
                      </select>
                      <label className="label">Status</label>
                      <select
                        className="select"
                        value={course.status}
                        onChange={(e) => handleChange('status', e.target.value)}
                      >
                        <option value="Draft">Draft</option>
                        <option value="Published">Published</option>
                        <option value="Archived">Archived</option>
                      </select>
                      <label className="label">Duration</label>
                      <input
                        type="text"
                        className="input"
                        value={course.duration}
                        onChange={(e) => handleChange('duration', e.target.value)}
                        placeholder="e.g. 8 weeks, 30 hours"
                        aria-describedby="duration-error"
                      />
                      <div className="section-divider" />
                      <h3>Pricing</h3>
                      <label className="label">
                        <input
                          type="checkbox"
                          checked={course.is_free}
                          onChange={handleFreeChange}
                          style={{ marginRight: 8 }}
                        />
                        This course is free
                      </label>
                      {/* Only show price fields if not free */}
                      {!course.is_free && (
                        <>
                          <label className="label">Price ({course.currency})</label>
                          <input
                            type="number"
                            className="input"
                            value={course.price}
                            onChange={(e) => handleChange('price', parseFloat(e.target.value) || 0)}
                            aria-describedby="price-error"
                          />
                          <label className="label">Discount Price (optional)</label>
                          <input
                            type="number"
                            className="input"
                            value={course.discount_price || ''}
                            onChange={(e) => handleChange('discount_price', e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="Enter discount price"
                            aria-describedby="discount-price-error"
                          />
                        </>
                      )}
                      <div className="section-divider" />
                      <div className="thumbnail-upload">
                        <label htmlFor="thumbnail-upload" className="action-btn">
                          <CloudUpload className="icon" /> Upload Thumbnail
                        </label>
                        <input
                          id="thumbnail-upload"
                          type="file"
                          style={{ display: 'none' }}
                          onChange={(e) => handleThumbnailChange(e.target.files[0])}
                          accept="image/*"
                        />
                        {course.thumbnailPreview && (
                          <div className="thumbnail-preview">
                            <img
                              src={course.thumbnailPreview}
                              alt="Thumbnail preview"
                              style={{ maxWidth: '200px', maxHeight: '200px', marginTop: '8px' }}
                            />
                          </div>
                        )}
                        {course.thumbnail && (
                          <div className="upload-preview">
                            <span>{course.thumbnail.name || 'Thumbnail selected'}</span>
                            <button
                              className="icon-btn danger"
                              type="button"
                              onClick={() => {
                                handleThumbnailChange(null);
                              }}
                            >
                              <Delete className="icon" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 1 && (
                  <div>
                    <h3>Course Modules</h3>
                    {course.modules.length === 0 && (
                      <div className="empty-state">
                        <School className="empty-icon" />
                        <h4>No modules added yet</h4>
                        <p>Add modules to structure your course content</p>
                        <button className="action-btn primary" type="button" onClick={addModule}>
                          <AddCircle className="icon" /> Add First Module
                        </button>
                      </div>
                    )}
                    <DndProvider backend={HTML5Backend}>
                      {course.modules.map((module, index) => (
                        <DraggableModule
                          key={module.id}
                          index={index}
                          module={module}
                          moveModule={moveModule}
                          selectedModules={selectedModules}
                          toggleModuleSelection={setSelectedModules}
                          onChange={handleModuleChange}
                          onDelete={deleteModule}
                          isMobile={isMobile}
                          courseId={id}
                        />
                      ))}
                    </DndProvider>
                    {course.modules.length > 0 && (
                      <button className="action-btn" type="button" onClick={addModule}>
                        <AddCircle className="icon" /> Add Another Module
                      </button>
                    )}
                  </div>
                )}

                {activeTab === 2 && (
                  <div>
                    <div className="section-header">
                      <h3>Course Instructors</h3>
                      <button
                        className="action-btn primary"
                        type="button"
                        onClick={() => setInstructorDialogOpen(true)}
                        disabled={!id && !course.id}
                      >
                        <People className="icon" /> Assign Instructor
                      </button>
                    </div>
                    {(!course.course_instructors || course.course_instructors.length === 0) ? (
                      <div className="empty-state">
                        <Person className="empty-icon" />
                        <h4>No instructors assigned</h4>
                        <p>Assign instructors to teach this course</p>
                        <button
                          className="action-btn primary"
                          type="button"
                          onClick={() => setInstructorDialogOpen(true)}
                          disabled={!id && !course.id}
                        >
                          <People className="icon" /> Assign Instructor
                        </button>
                      </div>
                    ) : (
                      <ul className="instructor-list compact grid">
                        {course.course_instructors.map((ci) => (
                          <li key={ci.id} className="instructor-item compact grid-item" tabIndex={0}>
                            <span className="avatar small">{ci.first_name?.charAt(0) || ci.email?.charAt(0) || "?"}</span>
                            <span className="instructor-name small">
                              {ci.first_name} {ci.last_name}
                            </span>
                            <span className="instructor-email-tooltip">{ci.email}</span>
                            <button
                              className="icon-btn danger"
                              title="Remove instructor"
                              onClick={() => handleRemoveInstructor(ci.id)}
                              style={{ marginLeft: 2, fontSize: 10, padding: 2 }}
                            >
                              ×
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {activeTab === 3 && (
                  <div>
                    <h3>Course Resources</h3>
                    <ul className="resource-list">
                      {course.resources.map((resource) => (
                        <li key={resource.id} className="resource-item">
                          <span className="resource-icon">
                            {resourceTypes.find(t => t.value === resource.type)?.icon || <InsertDriveFile />}
                          </span>
                          <div>
                            <span className="resource-title">{resource.title}</span>
                            <p className="resource-details">
                              {resource.type === 'link' ? resource.url : resource.file?.name || resource.file}
                            </p>
                          </div>
                          <div className="resource-actions">
                            <button
                              className="icon-btn"
                              type="button"
                              onClick={() => {
                                setCurrentResource(resource);
                                setResourceDialogOpen(true);
                              }}
                            >
                              <Edit className="icon" />
                            </button>
                            <button
                              className="icon-btn danger"
                              type="button"
                              onClick={() => deleteResource(resource.id)}
                            >
                              <Delete className="icon" />
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <button
                      className="action-btn"
                      type="button"
                      onClick={() => {
                        setCurrentResource({ id: null, title: '', type: 'link', url: '', file: null });
                        setResourceDialogOpen(true);
                      }}
                    >
                      <AddCircle className="icon" /> Add Resource
                    </button>
                  </div>
                )}

                {activeTab === 4 && <LearningPaths courseId={id} isMobile={isMobile} />}
                {activeTab === 5 && <CertificateSettings courseId={id} isMobile={isMobile} />}
                {activeTab === 6 && (
                  <div>
                    <h3>SCORM Settings</h3>
                    <div className="cv-card" style={{ marginBottom: 24 }}>
                      <label style={{ fontWeight: 500, marginBottom: 8, display: 'block' }}>
                        Upload SCORM Package (.zip)
                      </label>
                      <input
                        type="file"
                        accept=".zip"
                        onChange={handleScormFileChange}
                        ref={fileInputRef}
                        style={{ marginBottom: 8 }}
                        disabled={scormUploading}
                      />
                      <button
                        className="action-btn primary"
                        onClick={handleScormUpload}
                        disabled={scormUploading}
                        style={{ marginLeft: 8 }}
                      >
                        Upload
                      </button>
                      {scormUploadMsg && (
                        <div style={{ marginTop: 8, color: scormUploadMsg.includes('success') ? 'green' : 'red' }}>
                          {scormUploadMsg}
                        </div>
                      )}
                    </div>
                    <div style={{ margin: '16px 0' }}>
                      <label style={{ fontWeight: 500, marginRight: 8 }}>Select Learner for Preview:</label>
                      <select
                        value={selectedLearnerId || ''}
                        onChange={e => setSelectedLearnerId(e.target.value)}
                        style={{ minWidth: 200 }}
                      >
                        {learners.map(user => (
                          <option key={user.id} value={user.id}>{user.email}</option>
                        ))}
                      </select>
                    </div>
                    <SCORMPlayer courseId={course.id} userId={selectedLearnerId} />
                  </div>
                )}
                {activeTab === 7 && <GamificationManager courseId={id} isMobile={isMobile} />}
                <div className="action-buttons">
                  <button
                    className="action-btn"
                    type="button"
                    onClick={() => setActiveTab(prev => Math.max(prev - 1, 0))}
                    disabled={activeTab === 0}
                  >
                    <ArrowBack className="icon" /> Previous
                  </button>
                  <button
                    className="action-btn primary"
                    type="button"
                    onClick={(e) => handleSave(e, false)}
                    disabled={loading}
                  >
                    {loading ? <span className="loading-spinner" /> : <><Save className="icon" /> Save</>}
                  </button>
                  {activeTab === tabLabels.length - 1 ? (
                    <button
                      className="action-btn primary"
                      type="button"
                      onClick={(e) => handleSave(e, true)}
                      disabled={loading}
                    >
                      {loading ? <span className="loading-spinner" /> : <><Save className="icon" /> {isEdit ? 'Update & Finish' : 'Create & Finish'}</>}
                    </button>
                  ) : (
                    <button
                      className="action-btn primary"
                      type="button"
                      onClick={() => setActiveTab(prev => Math.min(prev + 1, tabLabels.length - 1))}
                    >
                      <ArrowBack className="icon rotate" /> Next
                    </button>
                  )}
                  <button
                    className="action-btn cancel"
                    type="button"
                    onClick={() => navigate('/admin/courses')}
                  >
                    <Cancel className="icon" /> Cancel
                  </button>
                </div>
              </form>
            )}
            {/* Resource Dialog */}
            <div className={`dialog ${resourceDialogOpen ? 'open' : ''}`} role="dialog" aria-labelledby="resource-dialog-title">
              <div className="dialog-overlay" onClick={() => setResourceDialogOpen(false)} />
              <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
                <div className="dialog-header">
                  <h3 id="resource-dialog-title">{currentResource?.id ? 'Edit Resource' : 'Add Resource'}</h3>
                  <button className="dialog-close" type="button" onClick={() => setResourceDialogOpen(false)}>
                    <Cancel className="icon" />
                  </button>
                </div>
                <form onSubmit={saveResource}>
                  <div className="dialog-body">
                    <label className="label">Resource Title</label>
                    <input
                      type="text"
                      className="input"
                      value={currentResource?.title}
                      onChange={(e) => setCurrentResource({ ...currentResource, title: e.target.value })}
                      placeholder="Enter resource title"
                      autoFocus
                      aria-describedby="resource-title-error"
                    />
                    <label className="label">Resource Type</label>
                    <select
                      className="select"
                      value={currentResource?.type}
                      onChange={(e) => setCurrentResource({ ...currentResource, type: e.target.value })}
                      aria-describedby="resource-type-error"
                    >
                      {resourceTypes.map(type => (
                        <option key={type.value} value={type.value}>{type.label}</option>
                      ))}
                    </select>
                    {currentResource?.type === 'link' && (
                      <>
                        <label className="label">URL</label>
                        <input
                          type="text"
                          className="input"
                          value={currentResource?.url}
                          onChange={(e) => setCurrentResource({ ...currentResource, url: e.target.value })}
                          placeholder="Enter resource URL"
                          aria-describedby="resource-url-error"
                        />
                      </>
                    )}
                    {(currentResource?.type === 'pdf' || currentResource?.type === 'video' || currentResource?.type === 'file') && (
                      <label htmlFor="resource-file-upload" className="action-btn">
                        <CloudUpload className="icon" /> {loading ? 'Uploading...' : 'Upload File'}
                        <input
                          id="resource-file-upload"
                          type="file"
                          onChange={(e) => setCurrentResource({ ...currentResource, file: e.target.files[0] })}
                          accept={currentResource?.type === 'pdf' ? 'application/pdf' : currentResource?.type === 'video' ? 'video/*' : '*/*'}
                        />
                      </label>
                    )}
                    {currentResource?.file && (
                      <span className="file-info">Selected: {currentResource?.file?.name}</span>
                    )}
                  </div>
                  <div className="dialog-actions">
                    <button className="action-btn" type="button" onClick={() => setResourceDialogOpen(false)}>
                      Cancel
                    </button>
                    <button
                      className="action-btn primary"
                      type="submit"
                      disabled={loading || !currentResource?.title?.trim()}
                    >
                      {loading ? <span className="loading-spinner" /> : 'Save'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
            {/* Category Dialog */}
            <div
              key={`category-dialog-${categoryDialogOpen}`}
              className={`dialog ${categoryDialogOpen ? 'open' : ''}`}
              role="dialog"
              aria-labelledby="category-dialog-title"
            >
              <div className="dialog-overlay" onClick={handleCloseCategoryDialog} />
              <div className="dialog-content" tabIndex="0" onClick={(e) => e.stopPropagation()}>
                <div className="dialog-header">
                  <h3 id="category-dialog-title">{editingCategory ? 'Edit Category' : 'Add Category'}</h3>
                  <button className="dialog-close" type="button" onClick={handleCloseCategoryDialog}>
                    <Cancel className="icon" />
                  </button>
                </div>
                <div className="dialog-body">
                  <form onSubmit={saveCategory}>
                    <label className="label">Category Name</label>
                    <input
                      type="text"
                      className="input"
                      key={`category-name-${categoryDialogOpen}`}
                      ref={categoryNameInputRef}
                      value={newCategory.name}
                      onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
                      placeholder="Enter category name"
                      aria-describedby="category-name-error"
                    />
                    {errors.categoryName && <span id="category-name-error" className="error-text">{errors.categoryName}</span>}
                    <label className="label">Description</label>
                    <textarea
                      className="textarea"
                      key={`category-description-${categoryDialogOpen}`}
                      value={newCategory.description}
                      onChange={(e) => setNewCategory({ ...newCategory, description: e.target.value })}
                      placeholder="Enter category description"
                      rows={3}
                      aria-describedby="category-description-error"
                    />
                    <div className="dialog-actions">
                      <button className="action-btn" type="button" onClick={handleCloseCategoryDialog}>
                        Cancel
                      </button>
                      <button
                        className="action-btn primary"
                        type="submit"
                        disabled={loading || !newCategory.name?.trim()}
                      >
                        {loading ? <span className="loading-spinner" /> : (editingCategory ? 'Update' : 'Add')}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
            {course && (id || course.id) && (
              <InstructorAssignmentDialog
                open={instructorDialogOpen}
                onClose={handleCloseInstructorDialog}
                modules={course.modules}
                courseId={course.id}
                course={course}
                onAssign={handleInstructorAssignment} // <-- fix here
              />
            )}
          </section>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default CourseForm;