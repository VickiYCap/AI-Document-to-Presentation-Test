import { useState } from 'react';
import { useContext } from 'react';
import './Homepage.css';
import { DataContext } from '../DataContext';
import { useNavigate } from 'react-router-dom';

function Homepage() {
  const [file, setFile] = useState(null);
  const{setParsedData} = useContext(DataContext);
  const navigate = useNavigate();
  
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
        console.log("This is the scraped data:\n", data);
        setParsedData(data)
        navigate('/testing');
      }
    } catch (err) {
      alert("Error uploading file: " + err.message);
    }
  };

  return (
    <>
    <div className='homepage-container'>
      <div className="navbar-container">
          <button onClick={() => navigate('/')}>Home</button>
          <button onClick={() => navigate('/policy-graph')}>Policy Graph</button>
          <button onClick={() => navigate('/presentation')}>Presentation Builder</button>
          <button onClick={() => navigate('/testing')}>Testing</button>
        </div>

      <h1>Welcome!</h1>
      <h2>What can I help with? </h2>
      <div className='search-query'>
        <input className='input-bar'></input>
        <button className='search-button'>Search</button>
      </div>
        <div style={{marginTop:"30px"}}> OR </div>

        <div className='file-upload'>
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