import os

# Base path
base_dir = "scorm_example"

# Directory structure
dirs = [
    base_dir,
    os.path.join(base_dir, "css"),
    os.path.join(base_dir, "js"),
    os.path.join(base_dir, "assets")
]

# File contents
files = {
    os.path.join(base_dir, "imsmanifest.xml"): '''<?xml version="1.0" standalone="no" ?>
<manifest identifier="SampleSCORM" version="1.0"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="ORG1">
    <organization identifier="ORG1">
      <title>Sample SCORM Course</title>
      <item identifier="ITEM1" identifierref="RES1">
        <title>Lesson 1: Introduction</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES1" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/>
      <file href="css/style.css"/>
      <file href="js/scorm.js"/>
      <file href="assets/sample_image.jpg"/>
    </resource>
  </resources>
</manifest>''',

    os.path.join(base_dir, "index.html"): '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sample SCORM Course</title>
  <link rel="stylesheet" href="css/style.css">
  <script src="js/scorm.js"></script>
</head>
<body onload="initSCORM()" onunload="terminateSCORM()">
  <div class="container">
    <h1>Welcome to the Sample SCORM Course</h1>
    <p>This is a simple SCORM 1.2 course example.</p>
    <img src="assets/sample_image.jpg" alt="Sample Image" class="sample-image">
    <button onclick="markComplete()">Mark as Complete</button>
  </div>
</body>
</html>''',

    os.path.join(base_dir, "css", "style.css"): '''body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 20px;
  background-color: #f4f4f4;
}
.container {
  max-width: 800px;
  margin: 0 auto;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}
h1 {
  color: #333;
}
.sample-image {
  max-width: 100%;
  height: auto;
  margin: 20px 0;
}
button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}
button:hover {
  background-color: #0056b3;
}''',

    os.path.join(base_dir, "js", "scorm.js"): '''let API = null;

function findAPI(win) {
  let attempts = 0;
  const maxAttempts = 500;
  while ((win.API == null || win.API === undefined) && attempts < maxAttempts) {
    if (win.parent && win.parent !== win) {
      win = win.parent;
    } else {
      return null;
    }
    attempts++;
  }
  return win.API;
}

function initSCORM() {
  API = findAPI(window);
  if (API) {
    const result = API.LMSInitialize("");
    if (result === "true") {
      console.log("SCORM API initialized successfully");
      API.LMSSetValue("cmi.core.lesson_status", "incomplete");
      API.LMSCommit("");
    } else {
      console.error("Failed to initialize SCORM API");
    }
  } else {
    console.error("SCORM API not found");
  }
}

function markComplete() {
  if (API) {
    API.LMSSetValue("cmi.core.lesson_status", "completed");
    API.LMSSetValue("cmi.core.score.raw", "80");
    API.LMSCommit("");
    alert("Course marked as complete!");
  }
}

function terminateSCORM() {
  if (API) {
    API.LMSFinish("");
    console.log("SCORM session terminated");
  }
}'''
}

# Create folders
for d in dirs:
    os.makedirs(d, exist_ok=True)

# Write files
for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# Dummy image
from PIL import Image

img_path = os.path.join(base_dir, "assets", "sample_image.jpg")
img = Image.new('RGB', (600, 400), color=(73, 109, 137))
img.save(img_path)

print(f"SCORM package directory structure created at: {os.path.abspath(base_dir)}")
