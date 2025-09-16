import React, { useState, useEffect, useRef } from 'react';
import './CourseView.css';
import {
  ArrowBack, Edit, People, Schedule, MonetizationOn, Assessment,
  VideoLibrary, Quiz, Assignment, PictureAsPdf, Description, Image, Link, Slideshow, YouTube, InsertDriveFile, CloudUpload
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { Document, Page } from 'react-pdf';
import { pdfjs } from 'react-pdf';
import { convertFromRaw } from 'draft-js';
import draftToHtml from 'draftjs-to-html';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { API_BASE_URL, userAPI, coursesAPI, scormAPI } from '../../../../config';
import SCORMPlayer from './SCORMPlayer';

// PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

// YouTube Player Component
const YouTubePlayer = ({ url, title }) => {
  const getYouTubeEmbedUrl = (url) => {
    try {
      const urlObj = new URL(url);
      let videoId = '';
      if (urlObj.hostname.includes('youtube.com')) {
        videoId = urlObj.searchParams.get('v') || '';
      } else if (urlObj.hostname.includes('youtu.be')) {
        videoId = urlObj.pathname.split('/')[1] || '';
      }
      return videoId ? `https://www.youtube.com/embed/${videoId}` : url;
    } catch {
      return url;
    }
  };
  return (
    <div className="responsive-iframe-container">
      <iframe
        className="media-iframe"
        src={getYouTubeEmbedUrl(url)}
        title={title}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
};

// PowerPoint Viewer Component
const PPTViewer = ({ url, title }) => (
  <div className="media-container">
    <iframe
      src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`}
      className="media-iframe"
      title={title}
    />
  </div>
);

// Video Player Component
const VideoPlayer = ({ url, title }) => (
  <div className="media-container">
    <video controls src={url} className="media" style={{ width: '100%', borderRadius: 10 }} />
  </div>
);

// PDF Viewer Component
const PDFViewer = ({ url, title }) => (
  <div className="media-container">
    <iframe src={url} className="media-iframe" title={title} />
  </div>
);

// Word Document Viewer Component
const WordViewer = ({ url, title }) => (
  <div className="media-container">
    <iframe
      src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`}
      className="media-iframe"
      title={title}
    />
  </div>
);

// Helper to resolve thumbnail URL
const resolveThumbnailUrl = (thumbnail) => {
  if (!thumbnail) return '/no-image.png';
  if (thumbnail.startsWith('http://') || thumbnail.startsWith('https://')) {
    return thumbnail;
  }
  if (thumbnail.startsWith('/media/')) {
    // Change this to your actual backend base URL
    const BASE_URL = API_BASE_URL;
    return `${BASE_URL}${thumbnail}`;
  }
  return thumbnail;
};

// Helper to resolve any media URL (local /media, S3, Supabase, etc.)
const resolveMediaUrl = (url) => {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  if (url.startsWith('/media/')) {
    const BASE_URL = API_BASE_URL;
    return `${BASE_URL}${url}`;
  }
  return url;
};

const CourseView = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [course, setCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeSection, setActiveSection] = useState('overview');
  const [expandedLesson, setExpandedLesson] = useState(null);
  const [scormFile, setScormFile] = useState(null);
  const [scormUploading, setScormUploading] = useState(false);
  const [scormUploadMsg, setScormUploadMsg] = useState('');
  const [learners, setLearners] = useState([]);
  const [selectedLearnerId, setSelectedLearnerId] = useState(null);
  const fileInputRef = useRef();

  const parseArrayField = (field) => {
    if (!field) return [];
    if (Array.isArray(field)) return field;
    if (typeof field === 'string') {
      try {
        const parsed = JSON.parse(field);
        return Array.isArray(parsed) ? parsed : [parsed];
      } catch {
        return [field];
      }
    }
    return [field];
  };

  const parseListField = (field) => {
    try {
      if (!field || !Array.isArray(field)) return [];
      return field.map(item => {
        try {
          const parsed = JSON.parse(item);
          return Array.isArray(parsed) ? parsed[0] : parsed;
        } catch {
          return item;
        }
      }).filter(item => typeof item === 'string' && item.trim());
    } catch (error) {
      return [];
    }
  };

  const convertDraftToHTML = (draftString) => {
    if (!draftString || typeof draftString !== 'string') {
      return { __html: DOMPurify.sanitize('No description available') };
    }
    if (draftString.trim().startsWith('{')) {
      try {
        const rawContent = JSON.parse(draftString);
        const contentState = convertFromRaw(rawContent);
        const htmlContent = draftToHtml(contentState);
        return { __html: DOMPurify.sanitize(htmlContent) };
      } catch (error) {
        // silent fail
      }
    }
    // Handle markdown or plain text
    try {
      const htmlContent = marked ? marked.parse(draftString) : draftString;
      return { __html: DOMPurify.sanitize(htmlContent) };
    } catch (error) {
      return { __html: DOMPurify.sanitize(draftString) };
    }
  };

  useEffect(() => {
    const fetchCourseData = async () => {
      setLoading(true);
      try {
        const response = await coursesAPI.getCourse(id);
        setCourse({
          ...response.data,
          learning_outcomes: parseListField(response.data.learning_outcomes),
          prerequisites: parseListField(response.data.prerequisites),
          modules: Array.isArray(response.data.modules)
            ? response.data.modules.map(module => ({
                ...module,
                lessons: Array.isArray(module.lessons)
                  ? module.lessons.map(lesson => ({
                      ...lesson,
                      content_file: lesson.content_file ? `${lesson.content_file}?t=${Date.now()}` : null,
                      content_url: lesson.content_url ? `${lesson.content_url}?t=${Date.now()}` : null
                    }))
                  : []
              }))
            : []
        });
        setError('');
      } catch (error) {
        console.error('Error fetching course:', error.response?.data || error.message);
        setError('Failed to load course data');
      } finally {
        setLoading(false);
      }
    };

    fetchCourseData();
  }, [id]);

  // Fetch learners for SCORM preview
  useEffect(() => {
    userAPI.getUsers({ role: 'learners', page_size: 100 }).then(res => {
      setLearners(res.data.results || []);
      if (res.data.results && res.data.results.length > 0) {
        setSelectedLearnerId(res.data.results[0].id);
      }
    });
  }, []);

  const handleBack = () => {
    navigate('/admin/courses');
  };

  const handleEdit = () => {
    navigate(`/admin/courses/edit/${id}`);
  };

  const formatPrice = (price, currency) => {
    const priceNumber = typeof price === 'string' ? parseFloat(price) : price;
    if (priceNumber === undefined || priceNumber === null || isNaN(priceNumber)) {
      return 'Price not set';
    }
    const currencyToUse = currency || 'NGN';
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currencyToUse
      }).format(priceNumber);
    } catch {
      return `${currencyToUse} ${priceNumber.toFixed(2)}`;
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'published': return '#4caf50';
      case 'draft': return '#f59e0b';
      case 'archived': return '#6b7280';
      default: return '#0288d1';
    }
  };

  const getLessonType = (lesson) => {
    if (lesson.lesson_type) {
      const type = lesson.lesson_type.toLowerCase();
      if (type === 'link' && lesson.content_url) {
        if (lesson.content_url.includes('youtube.com') || lesson.content_url.includes('youtu.be')) {
          return 'youtube';
        }
      }
      if (type === 'file') {
        const url = lesson.content_file || lesson.content_url || '';
        const extension = url.split('.').pop()?.toLowerCase();
        if (['ppt', 'pptx'].includes(extension)) return 'powerpoint';
        if (['doc', 'docx'].includes(extension)) return 'word';
        if (extension === 'pdf') return 'pdf';
      }
      return type;
    }
    const url = lesson.content_file || lesson.content_url || '';
    const extension = url.split('.').pop()?.toLowerCase();
    if (['mp4', 'webm', 'ogg'].includes(extension)) return 'video';
    if (extension === 'pdf') return 'pdf';
    if (['doc', 'docx'].includes(extension)) return 'word';
    if (['ppt', 'pptx'].includes(extension)) return 'powerpoint';
    if (['jpg', 'jpeg', 'png', 'gif'].includes(extension)) return 'image';
    if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
    return 'default';
  };

  const getLessonIcon = (type) => {
    const normalizedType = type.toLowerCase();
    switch (normalizedType) {
      case 'video': return <VideoLibrary className="icon primary" />;
      case 'quiz': return <Quiz className="icon secondary" />;
      case 'assignment': return <Assignment className="icon info" />;
      case 'pdf': return <PictureAsPdf className="icon error" />;
      case 'word': return <Description className="icon info" />;
      case 'powerpoint': return <Slideshow className="icon secondary" />;
      case 'image': return <Image className="icon success" />;
      case 'youtube': return <YouTube className="icon primary" />;
      case 'link': return <Link className="icon primary" />;
      case 'text': return <InsertDriveFile className="icon action" />;
      default: return <InsertDriveFile className="icon action" />;
    }
  };

  const getResourceIcon = (type) => {
    const normalizedType = type?.toLowerCase();
    switch (normalizedType) {
      case 'video': return <VideoLibrary className="icon primary" />;
      case 'pdf': return <PictureAsPdf className="icon error" />;
      case 'file': return <Description className="icon info" />;
      case 'powerpoint': return <Slideshow className="icon secondary" />;
      case 'image': return <Image className="icon success" />;
      case 'youtube': return <YouTube className="icon primary" />;
      case 'link': return <Link className="icon primary" />;
      default: return <InsertDriveFile className="icon action" />;
    }
  };

  // SCORM upload handler
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
      await scormAPI.uploadPackage(course.id, formData);
      setScormUploadMsg('SCORM package uploaded successfully!');
      setScormFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setScormUploadMsg('Upload failed. Please try again.');
    }
    setScormUploading(false);
  };

  if (loading) {
    return (
      <div className="cv-drastic-loading">
        <div className="cv-spinner" />
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="cv-drastic-error">
        <span>{error || 'Course not found'}</span>
      </div>
    );
  }

  return (
    <div className="cv-drastic-root">
      {/* Sidebar */}
      <aside className="cv-drastic-sidebar">
        <button className="cv-back-btn" onClick={() => navigate('/admin/courses')}>
          <ArrowBack /> <span>Back to Courses</span>
        </button>
        <div className="cv-sidebar-section">
          <img
            src={resolveThumbnailUrl(course.thumbnail)}
            alt={course.title}
            className="cv-course-thumb"
          />
          <h2 className="cv-course-title">{course.title}</h2>
          <span className={`cv-status-badge cv-status-${course.status?.toLowerCase()}`}>{course.status}</span>
          <button className="cv-edit-btn" onClick={() => navigate(`/admin/courses/edit/${id}`)}>
            <Edit /> Edit Course
          </button>
        </div>
        <nav className="cv-sidebar-nav">
          <button className={activeSection === 'overview' ? 'active' : ''} onClick={() => setActiveSection('overview')}>Overview</button>
          <button className={activeSection === 'modules' ? 'active' : ''} onClick={() => setActiveSection('modules')}>Modules</button>
          <button className={activeSection === 'resources' ? 'active' : ''} onClick={() => setActiveSection('resources')}>Resources</button>
          <button className={activeSection === 'meta' ? 'active' : ''} onClick={() => setActiveSection('meta')}>Meta</button>
          <button className={activeSection === 'scorm' ? 'active' : ''} onClick={() => setActiveSection('scorm')}>SCORM</button>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="cv-drastic-main">
        {activeSection === 'overview' && (
          <section className="cv-section">
            <h3>Course Description</h3>
            <div className="cv-description" dangerouslySetInnerHTML={convertDraftToHTML(course.description)} />
            <div className="cv-flex-row">
              <div className="cv-card">
                <h4>Learning Outcomes</h4>
                <ul>
                  {parseArrayField(course.learning_outcomes).map((outcome, i) => <li key={i}>{outcome}</li>)}
                </ul>
              </div>
              <div className="cv-card">
                <h4>Prerequisites</h4>
                <ul>
                  {parseArrayField(course.prerequisites).map((prereq, i) => <li key={i}>{prereq}</li>)}
                </ul>
              </div>
            </div>
          </section>
        )}

        {activeSection === 'modules' && (
          <section className="cv-section">
            <h3>Modules & Lessons</h3>
            {course.modules && course.modules.length > 0 ? (
              course.modules.map(module => (
                <div key={module.id} className="cv-module-card">
                  <div className="cv-module-header">
                    <h4>{module.title}</h4>
                    <span>{module.lessons.length} Lessons</span>
                  </div>
                  <p className="cv-module-desc">{module.description}</p>
                  <ul className="cv-lesson-list">
                    {module.lessons.length > 0 ? (
                      module.lessons.map(lesson => {
                        const lessonType = getLessonType(lesson);
                        const contentUrl = lesson.content_file || lesson.content_url;
                        return (
                          <li key={lesson.id} className={`cv-lesson-item${expandedLesson === lesson.id ? ' expanded' : ''}`}>
                            <div className="cv-lesson-header" onClick={() => setExpandedLesson(expandedLesson === lesson.id ? null : lesson.id)}>
                              <span className="cv-lesson-icon">{getLessonIcon(lessonType)}</span>
                              <div>
                                <span className="cv-lesson-title">{lesson.title}</span>
                                <span className="cv-lesson-meta">{lesson.duration || lessonType}</span>
                              </div>
                            </div>
                            {expandedLesson === lesson.id && (
                              <div className="cv-lesson-content-area">
                                <div className="cv-lesson-content-title">{lesson.title}</div>
                                <div className="cv-lesson-content">
                                  {/* Text/HTML/Markdown */}
                                  {lessonType === 'text' && (
                                    <div dangerouslySetInnerHTML={convertDraftToHTML(lesson.content_text)} />
                                  )}

                                  {/* YouTube */}
                                  {lessonType === 'youtube' && (
                                    <YouTubePlayer url={resolveMediaUrl(lesson.content_url || lesson.content_file)} title={lesson.title} />
                                  )}

                                  {/* Video */}
                                  {lessonType === 'video' && (
                                    <VideoPlayer url={resolveMediaUrl(lesson.content_url || lesson.content_file)} title={lesson.title} />
                                  )}

                                  {/* PDF */}
                                  {lessonType === 'pdf' && (
                                    <PDFViewer url={resolveMediaUrl(lesson.content_url || lesson.content_file)} title={lesson.title} />
                                  )}

                                  {/* PowerPoint */}
                                  {lessonType === 'powerpoint' && (
                                    <PPTViewer url={resolveMediaUrl(lesson.content_url || lesson.content_file)} title={lesson.title} />
                                  )}

                                  {/* Word */}
                                  {lessonType === 'word' && (
                                    <WordViewer url={resolveMediaUrl(lesson.content_url || lesson.content_file)} title={lesson.title} />
                                  )}

                                  {/* Image */}
                                  {lessonType === 'image' && (
                                    <div className="media-container">
                                      <img
                                        src={resolveMediaUrl(lesson.content_url || lesson.content_file)}
                                        alt={lesson.title}
                                        className="media"
                                        style={{ maxWidth: '100%', borderRadius: 10 }}
                                      />
                                    </div>
                                  )}

                                  {/* Link */}
                                  {lessonType === 'link' && (
                                    <div className="media-container">
                                      <a
                                        href={resolveMediaUrl(lesson.content_url || lesson.content_file)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="action-btn primary"
                                      >
                                        Visit Link
                                      </a>
                                    </div>
                                  )}

                                  {/* Fallback */}
                                  {lessonType === 'default' && (lesson.content_url || lesson.content_file) && (
                                    <div className="media-container">
                                      <a
                                        href={resolveMediaUrl(lesson.content_url || lesson.content_file)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="action-btn primary"
                                      >
                                        Download Resource
                                      </a>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </li>
                        );
                      })
                    ) : (
                      <li className="cv-lesson-empty">No lessons available</li>
                    )}
                  </ul>
                </div>
              ))
            ) : (
              <div className="cv-empty">No modules available</div>
            )}
          </section>
        )}

        {activeSection === 'resources' && (
          <section className="cv-section">
            <h3>Course Resources</h3>
            <ul className="cv-resource-list">
              {course.resources && course.resources.length > 0 ? (
                course.resources.map(resource => {
                  const resourceUrl = resolveMediaUrl(resource.url || resource.file);
                  const resourceType = resource.resource_type === 'file' && resourceUrl.match(/\.(ppt|pptx)$/i) ? 'powerpoint' :
                    resource.resource_type === 'link' && resourceUrl.match(/youtube\.com|youtu\.be/) ? 'youtube' :
                    resource.resource_type;
                  return (
                    <li key={resource.id} className="cv-resource-item">
                      <div className="cv-resource-header">
                        <span className="cv-resource-icon">{getResourceIcon(resourceType)}</span>
                        <div>
                          <span className="cv-resource-title">{resource.title}</span>
                          <span className="cv-resource-meta">{resourceType}</span>
                        </div>
                        <a href={resourceUrl} target="_blank" rel="noopener noreferrer" className="action-btn">Open</a>
                      </div>
                    </li>
                  );
                })
              ) : (
                <li className="cv-empty">No resources available</li>
              )}
            </ul>
          </section>
        )}

        {activeSection === 'meta' && (
          <section className="cv-section">
            <h3>Course Meta Information</h3>
            <div className="cv-meta-grid">
              <div className="cv-meta-card">
                <People className="icon" /> <span>Students</span>
                <strong>{course.total_enrollments || 0}</strong>
              </div>
              <div className="cv-meta-card">
                <Schedule className="icon" /> <span>Duration</span>
                <strong>{course.duration || 'Not specified'}</strong>
              </div>
              <div className="cv-meta-card">
                <MonetizationOn className="icon" /> <span>Price</span>
                <strong>
                  {course.is_free ? (
                    <span style={{ color: "#4caf50", fontWeight: 600 }}>Free</span>
                  ) : course.discount_price ? (
                    <>
                      <span className="cv-price-strike">{formatPrice(course.price, course.currency)}</span>
                      <span className="cv-price-discount">{formatPrice(course.discount_price, course.currency)}</span>
                    </>
                  ) : (
                    formatPrice(course.price, course.currency)
                  )}
                </strong>
              </div>
              <div className="cv-meta-card">
                <Assessment className="icon" /> <span>Status</span>
                <span className={`cv-status-badge cv-status-${course.status?.toLowerCase()}`}>{course.status}</span>
              </div>
              <div className="cv-meta-card">
                <span>Course Code</span>
                <strong>{course.code}</strong>
              </div>
              <div className="cv-meta-card">
                <span>Category</span>
                <strong>{course.category?.name || 'Not specified'}</strong>
              </div>
              <div className="cv-meta-card">
                <span>Level</span>
                <strong>{course.level}</strong>
              </div>
              <div className="cv-meta-card">
                <span>Created</span>
                <strong>{new Date(course.created_at).toLocaleDateString()}</strong>
              </div>
              <div className="cv-meta-card">
                <span>Last Updated</span>
                <strong>{new Date(course.updated_at).toLocaleDateString()}</strong>
              </div>
            </div>
          </section>
        )}

        {activeSection === 'scorm' && (
          <section className="cv-section">
            <h3>SCORM Course Player</h3>
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
            {course.id && (
              <SCORMPlayer courseId={course.id} userId={selectedLearnerId} />
            )}
          </section>
        )}
      </main>
    </div>
  );
};

export default CourseView;