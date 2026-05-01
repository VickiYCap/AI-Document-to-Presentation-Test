import { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Homepage.css';
import { FaFilePdf, FaFilePowerpoint } from 'react-icons/fa';
import { HiPresentationChartBar } from "react-icons/hi";
import { DataContext } from '../DataContext';

function SlideCard({ type }) {
  if (type === 0) return (
    <div className='slide-card'>
      <div className='slide-header-bar' />
      <div className='slide-line' style={{ width: '55%' }} />
      <div className='slide-bars'>
        <div className='slide-bar' style={{ height: '60%' }} />
        <div className='slide-bar' style={{ height: '85%' }} />
        <div className='slide-bar' style={{ height: '40%' }} />
        <div className='slide-bar' style={{ height: '70%' }} />
        <div className='slide-bar' style={{ height: '55%' }} />
      </div>
    </div>
  );

  if (type === 1) return (
    <div className='slide-card'>
      <div className='slide-header-bar' />
      <div className='slide-split'>
        <div className='slide-split-text'>
          <div className='slide-line' style={{ width: '90%' }} />
          <div className='slide-line' style={{ width: '75%' }} />
          <div className='slide-line' style={{ width: '85%' }} />
          <div className='slide-line' style={{ width: '60%' }} />
          <div className='slide-line' style={{ width: '80%' }} />
        </div>
        <div className='slide-image-placeholder' />
      </div>
    </div>
  );

  return (
    <div className='slide-card'>
      <div className='slide-header-bar' />
      <div className='slide-line' style={{ width: '70%' }} />
      <div className='slide-line' style={{ width: '50%' }} />
      <div className='slide-body-block' />
      <div className='slide-line' style={{ width: '60%' }} />
    </div>
  );
}

function Homepage() {
  const { pdfFile, setPdfFile, pptxFile, setPptxFile, setTemplateImages, stylePrompt, setStylePrompt } = useContext(DataContext);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handlePptxUpload(file) {
    setPptxFile(file);
    setTemplateImages(null);
    if (!file) return;
    setPreviewLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('pptx_file', file);
      const res = await fetch('http://localhost:8000/analyze-template', { method: 'POST', body: form });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setTemplateImages(data.slides);
    } catch (e) {
      setError(`Template analysis failed: ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  }

  function handleNext() {
    if (!pdfFile || !pptxFile) {
      setError('Please upload both a PDF and a PPTX template.');
      return;
    }
    setError(null);
    navigate('/presentation');
  }

  return (
    <>
    <div className='homepage-container'>
        <div className='header'>
          <div className='header-title'>
            <HiPresentationChartBar size={64} color= "#1575DB"/>
            <h1>Turn Any Document into a Presentation</h1>
          </div>
          <p>Upload a file and a template or enter a prompt — we'll handle the rest!</p>
        </div>

        <div className='uploads'>
          <div className='file-upload-container'>
            <div className='upload-label'>Upload File</div>
            <FaFilePdf size={64} style={{ color: "#1575DB", marginTop: "20px" }} className='upload-icon' />
            <div className='upload-sublabel'>{pdfFile ? pdfFile.name : 'No file selected'}</div>
            <div className='file-upload'>
              <input id="file-input" type="file" name="file" onChange={(e) => setPdfFile(e.target.files[0])}/>
              <label htmlFor="file-input" className='select-btn'>Select File</label>
              <p className='upload-hint'>Supported formats: PDF</p>
            </div>
          </div>

          <div className='file-upload-container'>
            <div className='upload-label'>Upload PPTX</div>
            <FaFilePowerpoint size={64} style={{ color: "#1575DB", marginTop: "20px" }} className='upload-icon' />
            <div className='upload-sublabel'>
              {pptxFile ? pptxFile.name : 'No file selected'}
              {previewLoading && <span style={{ color: '#1575DB', fontSize: '0.8rem' }}> Analysing…</span>}
            </div>
            <div className='file-upload'>
              <input id="pptx-input" type="file" name="file" accept=".pptx" onChange={(e) => handlePptxUpload(e.target.files[0])}/>
              <label htmlFor="pptx-input" className='select-btn'>Select File</label>
              <p className='upload-hint'>Supported formats: PPTX</p>
            </div>
          </div>
          <div className='file-upload-container' style={{border:"solid"}}>
            <textarea
              className='prompt-input'
              placeholder='Enter a prompt (e.g. "corporate", "minimalist", "creative")'
              value={stylePrompt}
              onChange={(e) => setStylePrompt(e.target.value)}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button
            onClick={handleNext}
            disabled={previewLoading}
            className='generate-btn'
          >
            {previewLoading ? 'Analysing template…' : 'Next'}
          </button>
        </div>

        {error && <p style={{ color: 'red', textAlign: 'center' }}>{error}</p>}

        <div className='presentation-template'>
          <div className='slide-track'>
            {[...Array(6)].map((_, i) => <SlideCard key={i} type={i % 3} />)}
            {[...Array(6)].map((_, i) => <SlideCard key={`clone-${i}`} type={i % 3} />)}
          </div>
        </div>
    </div>
    </>
  );
}

export default Homepage;
