import { useContext, useState } from 'react';
import './Powerpoint.css';
import { HiPresentationChartBar } from "react-icons/hi";
import { FaFilePdf, FaFilePowerpoint, FaImage } from 'react-icons/fa';
import { DataContext } from '../DataContext';

function Powerpoint() {
    const { pdfFile, pptxFile, templateImages, imageReplacements, setImageReplacements, stylePrompt } = useContext(DataContext);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [generatedSlides, setGeneratedSlides] = useState([]);
    const [pptxDownloadUrl, setPptxDownloadUrl] = useState(null);
    const [pdfDownloadUrl, setPdfDownloadUrl] = useState(null);

    function b64toBlob(b64, mime) {
        const bytes = atob(b64);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        return new Blob([arr], { type: mime });
    }

    async function handleGenerate() {
        setError(null);
        setPptxDownloadUrl(null);
        setPdfDownloadUrl(null);
        setGeneratedSlides([]);
        setLoading(true);
        try {
            const form = new FormData();
            form.append('pdf_file', pdfFile);
            form.append('pptx_file', pptxFile);

            const meta = [];
            for (const { file, slideIndex, shapeId } of Object.values(imageReplacements)) {
                meta.push({ slide_index: slideIndex, shape_id: shapeId });
                form.append('image_files', file);
            }
            form.append('image_meta', JSON.stringify(meta));
            form.append('style_prompt', stylePrompt || '');

            const res = await fetch('http://localhost:8000/generate', { method: 'POST', body: form });
            if (!res.ok) {
                const detail = await res.json().catch(() => ({}));
                throw new Error(detail.detail || `Server error ${res.status}`);
            }
            const data = await res.json();

            if (data.pptx_base64) {
                const blob = b64toBlob(data.pptx_base64, 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
                setPptxDownloadUrl(URL.createObjectURL(blob));
            }
            if (data.pdf_base64) {
                const blob = b64toBlob(data.pdf_base64, 'application/pdf');
                setPdfDownloadUrl(URL.createObjectURL(blob));
            }
            if (data.slides?.length) {
                setGeneratedSlides(data.slides);
            }
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    function handleReplace(slideIndex, shapeId, file) {
        if (!file) return;
        setImageReplacements(prev => ({
            ...prev,
            [`${slideIndex}_${shapeId}`]: { file, slideIndex, shapeId },
        }));
    }

    function handleRemove(slideIndex, shapeId) {
        setImageReplacements(prev => {
            const next = { ...prev };
            delete next[`${slideIndex}_${shapeId}`];
            return next;
        });
    }

    const totalReplacements = Object.keys(imageReplacements).length;

    return (
        <div className="powerpoint-container">
            <div className='generation-info'>
                <div className='header'>
                    <div className='header-title'>
                        <HiPresentationChartBar size={32} style={{ color: "#1575DB" }} />
                        <h1>Turn Any Document into a Presentation</h1>
                    </div>
                    <p>Before we generate your presentation, feel free to replace images on any slide.</p>
                </div>

                <div className='file-container'>
                    <FaFilePdf size={32} style={{ color: "#1575DB", marginTop: "20px" }} className='upload-icon' />
                    <div>{pdfFile ? pdfFile.name : 'No file uploaded'}</div>
                </div>
                <div className='file-container'>
                    <FaFilePowerpoint size={32} style={{ color: "#1575DB", marginTop: "20px" }} className='upload-icon' />
                    <div>{pptxFile ? pptxFile.name : 'No template uploaded'}</div>
                </div>

                {totalReplacements > 0 && (
                    <div className='replacement-summary'>
                        <FaImage size={16} style={{ color: "#e53935" }} />
                        <span>{totalReplacements} image{totalReplacements > 1 ? 's' : ''} queued for replacement</span>
                    </div>
                )}

                <p className='info-hint'>
                    Hover over highlighted regions on any slide to replace its image. Slides without images are shown for reference only.
                </p>

                <button onClick={handleGenerate} disabled={loading} className='generate-btn'>
                    {loading ? 'Generating…' : 'Generate'}
                </button>

                {error && <p className='generate-error'>{error}</p>}

                {pptxDownloadUrl && (
                    <a href={pptxDownloadUrl} download="presentation.pptx" className='download-link'>
                        ⬇ Download PPTX
                    </a>
                )}
                {pdfDownloadUrl && (
                    <a href={pdfDownloadUrl} download="presentation.pdf" className='download-link'>
                        ⬇ Download PDF
                    </a>
                )}
            </div>

            <div className='powerpoint-display'>
                {generatedSlides.length > 0 ? (
                    <div className='slides-grid'>
                        {generatedSlides.map((slide) => (
                            <div key={slide.slide_index} className='slide-thumb-card'>
                                <div className='slide-thumb-label'>Slide {slide.slide_index + 1}</div>
                                <div className='slide-thumb-wrapper'>
                                    <img
                                        src={slide.thumbnail}
                                        alt={`Slide ${slide.slide_index + 1}`}
                                        className='slide-thumb-img'
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : templateImages ? (
                    <div className='slides-grid'>
                        {templateImages.map((slide) => (
                            <div key={slide.slide_key} className='slide-thumb-card'>
                                <div className='slide-thumb-label'>Slide {slide.slide_index + 1}</div>
                                <div className='slide-thumb-wrapper'>
                                    <img
                                        src={slide.thumbnail}
                                        alt={`Slide ${slide.slide_index + 1}`}
                                        className='slide-thumb-img'
                                    />
                                    {slide.images.map((img) => {
                                        const key = `${slide.slide_index}_${img.shape_id}`;
                                        const replacement = imageReplacements[key];
                                        return (
                                            <div
                                                key={img.shape_id}
                                                className={`image-overlay-box${replacement ? ' replaced' : ''}`}
                                                style={{
                                                    left: `${img.left_pct * 100}%`,
                                                    top: `${img.top_pct * 100}%`,
                                                    width: `${img.width_pct * 100}%`,
                                                    height: `${img.height_pct * 100}%`,
                                                }}
                                            >
                                                {replacement ? (
                                                    <div className='overlay-replaced'>
                                                        <img
                                                            src={URL.createObjectURL(replacement.file)}
                                                            alt="replacement"
                                                            className='overlay-preview-img'
                                                        />
                                                        <button
                                                            className='overlay-remove-btn'
                                                            onClick={() => handleRemove(slide.slide_index, img.shape_id)}
                                                            title="Remove replacement"
                                                        >×</button>
                                                    </div>
                                                ) : (
                                                    <label className='overlay-upload-label'>
                                                        <input
                                                            type="file"
                                                            accept="image/*"
                                                            style={{ display: 'none' }}
                                                            onChange={(e) => handleReplace(slide.slide_index, img.shape_id, e.target.files[0])}
                                                        />
                                                        <FaImage size={14} />
                                                        <span>Replace</span>
                                                    </label>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className='no-template-msg'>No template selected — upload a PPTX on the home page first.</p>
                )}
            </div>
        </div>
    );
}

export default Powerpoint;
