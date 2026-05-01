import './App.css';
import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { DataContext } from './DataContext';

import Homepage from './components/Homepage';
import Powerpoint from './components/Powerpoint';


function App() {
  const [templateImages, setTemplateImages] = useState(null);
  const [imageReplacements, setImageReplacements] = useState({});
  const [pdfFile, setPdfFile] = useState(null);
  const [pptxFile, setPptxFile] = useState(null);
  const [stylePrompt, setStylePrompt] = useState('');

  return (
    <DataContext.Provider value={{
      templateImages, setTemplateImages,
      imageReplacements, setImageReplacements,
      pdfFile, setPdfFile,
      pptxFile, setPptxFile,
      stylePrompt, setStylePrompt,
    }}>
      <Router>
        <Routes>
          <Route path="/" element={<Homepage />} />
          <Route path="/presentation" element={<Powerpoint />} />
        </Routes>
      </Router>
    </DataContext.Provider>
  );
}

export default App;
