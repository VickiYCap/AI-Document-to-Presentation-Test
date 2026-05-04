import { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaFilePdf, FaFilePowerpoint } from 'react-icons/fa';
import { HiPresentationChartBar } from "react-icons/hi";
import { DataContext } from '../DataContext';

{/**Function for moving presentation UI */}
function SlideCard({ type }) {
  if (type === 0) return (
    <div className='w-[400px] h-[300px] bg-white rounded-lg p-4 shadow-[0_2px_8px_rgba(0,0,0,0.1)] shrink-0 flex flex-col gap-2'>
      <div className='h-[14px] bg-primary rounded w-full opacity-80' />
      <div className='h-2 bg-slide-rule rounded' style={{ width: '55%' }} />
      <div className='flex flex-row items-end gap-[10px] flex-1 pt-2 border-b-2 border-slide-rule'>
        <div className='flex-1 bg-primary [border-radius:3px_3px_0_0] opacity-75' style={{ height: '60%' }} />
        <div className='flex-1 bg-primary [border-radius:3px_3px_0_0] opacity-75' style={{ height: '85%' }} />
        <div className='flex-1 bg-primary [border-radius:3px_3px_0_0] opacity-75' style={{ height: '40%' }} />
        <div className='flex-1 bg-primary [border-radius:3px_3px_0_0] opacity-75' style={{ height: '70%' }} />
        <div className='flex-1 bg-primary [border-radius:3px_3px_0_0] opacity-75' style={{ height: '55%' }} />
      </div>
    </div>
  );

  if (type === 1) return (
    <div className='w-[400px] h-[300px] bg-white rounded-lg p-4 shadow-[0_2px_8px_rgba(0,0,0,0.1)] shrink-0 flex flex-col gap-2'>
      <div className='h-[14px] bg-primary rounded w-full opacity-80' />
      <div className='flex flex-row gap-3 flex-1 pt-2'>
        <div className='flex-1 flex flex-col gap-2 justify-center'>
          <div className='h-2 bg-slide-rule rounded' style={{ width: '90%' }} />
          <div className='h-2 bg-slide-rule rounded' style={{ width: '75%' }} />
          <div className='h-2 bg-slide-rule rounded' style={{ width: '85%' }} />
          <div className='h-2 bg-slide-rule rounded' style={{ width: '60%' }} />
          <div className='h-2 bg-slide-rule rounded' style={{ width: '80%' }} />
        </div>
        <div className='flex-1 bg-slide-placeholder rounded-md border-2 border-dashed border-slide-placeholder-border' />
      </div>
    </div>
  );

  return (
    <div className='w-[400px] h-[300px] bg-white rounded-lg p-4 shadow-[0_2px_8px_rgba(0,0,0,0.1)] shrink-0 flex flex-col gap-2'>
      <div className='h-[14px] bg-primary rounded w-full opacity-80' />
      <div className='h-2 bg-slide-rule rounded' style={{ width: '70%' }} />
      <div className='h-2 bg-slide-rule rounded' style={{ width: '50%' }} />
      <div className='h-10 bg-slide-block rounded-md my-1' />
      <div className='h-2 bg-slide-rule rounded' style={{ width: '60%' }} />
    </div>
  );
}

function Homepage() {
  const { pdfFile, setPdfFile, pptxFile, setPptxFile, setTemplateImages, stylePrompt, setStylePrompt, setPdfImages } = useContext(DataContext);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handlePdfUpload(file) {
    setPdfFile(file);
    setPdfImages(null);
    if (!file) return;
    try {
      const form = new FormData();
      form.append('pdf_file', file);
      const res = await fetch('http://localhost:8000/pdf-images', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        setPdfImages(data.images);
      }
    } catch {
    }
  }

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
    <div className='flex flex-col items-center h-screen w-full bg-surface pt-[10px]'>
      <div className='text-left mb-10'>
        <div className='flex flex-row items-center gap-5 -ml-[90px]'>
          <HiPresentationChartBar size={64} color="var(--color-primary)" />
          <h1 className='text-[2rem] font-normal text-secondary mt-0 mb-3'>Turn Any Document into a Presentation</h1>
        </div>
        <p className='text-[1.1rem] text-muted m-0'>Upload a file and a template or enter a prompt — we'll handle the rest!</p>
      </div>

      <div className='flex flex-row justify-center w-full gap-[50px]'>
        <div className='flex flex-col items-center justify-center border-2 border-dashed border-primary p-[10px] rounded-[30px] text-primary w-[230px] h-[230px]'>
          <div className='text-base font-semibold text-secondary'>Upload File</div>
          <FaFilePdf size={64} style={{ color: "var(--color-primary)", marginTop: "20px" }} className='mb-3' />
          <div className='text-[0.85rem] text-subtle mb-3'>{pdfFile ? pdfFile.name : 'No file selected'}</div>
          <div className='text-primary mt-5 flex flex-col items-center justify-between'>
            <input id="file-input" type="file" name="file" className='hidden' onChange={(e) => handlePdfUpload(e.target.files[0])} />
            <label htmlFor="file-input" className='inline-block px-5 py-2 bg-primary text-white border-2 border-primary rounded-lg cursor-pointer text-[0.9rem] max-w-[160px] overflow-hidden text-ellipsis whitespace-nowrap hover:bg-white hover:text-primary'>Select File</label>
            <p className='text-[0.7rem] text-secondary mt-[10px] italic'>Supported formats: PDF</p>
          </div>
        </div>

        <div className='flex flex-col items-center justify-center border-2 border-dashed border-primary p-[10px] rounded-[30px] text-primary w-[230px] h-[230px]'>
          <div className='text-base font-semibold text-secondary'>Upload PPTX</div>
          <FaFilePowerpoint size={64} style={{ color: "var(--color-primary)", marginTop: "20px" }} className='mb-3' />
          <div className='text-[0.85rem] text-subtle mb-3'>
            {pptxFile ? pptxFile.name : 'No file selected'}
            {previewLoading && <span className='text-primary text-[0.8rem]'> Analysing…</span>}
          </div>
          <div className='text-primary mt-5 flex flex-col items-center justify-between'>
            <input id="pptx-input" type="file" name="file" accept=".pptx" className='hidden' onChange={(e) => handlePptxUpload(e.target.files[0])} />
            <label htmlFor="pptx-input" className='inline-block px-5 py-2 bg-primary text-white border-2 border-primary rounded-lg cursor-pointer text-[0.9rem] max-w-[160px] overflow-hidden text-ellipsis whitespace-nowrap hover:bg-white hover:text-primary'>Select File</label>
            <p className='text-[0.7rem] text-secondary mt-[10px] italic'>Supported formats: PPTX</p>
          </div>
        </div>

        <div className='flex flex-col items-center justify-center border-2 border-primary p-[10px] rounded-[30px] text-primary w-[230px] h-[230px]'>
          <textarea
            className='py-[10px] px-[15px] border-0 text-base h-full w-full text-secondary bg-surface align-top resize-none font-[inherit] box-border outline-none'
            placeholder='Enter a prompt (e.g. "Make it more casual and fun!")'
            value={stylePrompt}
            onChange={(e) => setStylePrompt(e.target.value)}
          />
        </div>
      </div>

      <div className='flex justify-center'>
        <button
          onClick={handleNext}
          disabled={previewLoading}
          className='mt-5 px-[30px] py-3 bg-primary text-white border-2 border-primary rounded-lg cursor-pointer text-base hover:bg-white hover:text-primary'
        >
          {previewLoading ? 'Analysing template…' : 'Next'}
        </button>
      </div>

      {error && <p className='text-red-500 text-center'>{error}</p>}

      <div className='mt-5 w-[70%] bg-canvas border border-canvas rounded-[15px] p-5 overflow-hidden'>
        <div className='flex flex-row gap-5 animate-scroll-left w-max opacity-70'>
          {[...Array(6)].map((_, i) => <SlideCard key={i} type={i % 3} />)}
          {[...Array(6)].map((_, i) => <SlideCard key={`clone-${i}`} type={i % 3} />)}
        </div>
      </div>
    </div>
    </>
  );
}

export default Homepage;
