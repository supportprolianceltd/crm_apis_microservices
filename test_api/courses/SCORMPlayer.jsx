import React, { useEffect, useRef, useState } from 'react';
import { scormAPI } from '../../../../config';


const SCORMPlayer = ({ courseId, userId }) => {
  const iframeRef = useRef();
  const [scormUrl, setScormUrl] = useState(null);

  // Inject SCORM API into iframe
  useEffect(() => {
    const handleLoad = () => {
      if (!iframeRef.current) return;
      const iframeWindow = iframeRef.current.contentWindow;
      if (!iframeWindow) return;

      // Minimal SCORM 1.2 API
      iframeWindow.API = {
        LMSInitialize: () => "true",
        LMSFinish: () => "true",
        LMSGetValue: (key) => "",
        LMSSetValue: (key, value) => {
          // Use extracted API
          scormAPI.track(courseId, { key, value, user_id: userId });
          return "true";
        },
        LMSCommit: () => "true",
        LMSGetLastError: () => "0",
        LMSGetErrorString: () => "",
        LMSGetDiagnostic: () => ""
      };
    };

    const iframe = iframeRef.current;
    if (iframe) {
      iframe.addEventListener('load', handleLoad);
      return () => iframe.removeEventListener('load', handleLoad);
    }
  }, [courseId, userId]);

  useEffect(() => {
    scormAPI.launch(courseId).then(res => {
      setScormUrl(res.data.public_url); // This comes from your backend JSON
    });
  }, [courseId]);

  console.log("SCORM URL:", scormUrl);

  return scormUrl ? (
    <div style={{ width: '100%', height: '80vh', background: '#f7f5ff', borderRadius: 10, overflow: 'hidden' }}>
      <iframe
        src={scormUrl}
        title="SCORM Player"
        width="100%"
        height="100%"
        style={{ border: 'none', minHeight: '80vh', background: '#fff' }}
        allowFullScreen
      />
    </div>
  ) : <div>Loading...</div>;
};

export default SCORMPlayer;