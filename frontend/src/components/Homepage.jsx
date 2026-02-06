import { useState } from 'react';
import './Homepage.css';
function Homepage() {
  const [file, setFile] = useState(null);

  
 const handleFileUpload = async (e) => {
    e.preventDefault();

    if (!file) {
      alert("Please select a file first!");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        alert("Upload failed: " + (data.detail || "Unknown error"));
      } else {
        alert("Upload successful! has reached backend.");
        console.log(data);
      }
    } catch (err) {
      alert("Error uploading file: " + err.message);
    }
  };

  return (
    <>
    <div className='homepage-container'>
      <h1>Welcome!</h1>
      <h2>What can I help with? </h2>
      <div className='search-query'>
        <input className='input-bar'></input>
        <button className='search-button'>Search</button>
      </div>
        <div style={{marginTop:"30px"}}> OR </div>

        <div className='file-upload'>y
          <div>Select a file to turn into a presentation</div>
          <form onSubmit={handleFileUpload}>
            <input type="file" name="file" onChange={(e) => setFile(e.target.files[0])}/>
            <input type="submit" value="Upload"/>
          </form>
        </div>

    </div>
    </>
  );
}

export default Homepage;