import { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HiPresentationChartBar } from "react-icons/hi";
import { FaFilePdf, FaFilePowerpoint, FaImage } from 'react-icons/fa';
import { IoCaretBack } from "react-icons/io5";
import { DataContext } from '../DataContext';

function Powerpoint() {
    const { pdfFile, pptxFile, templateImages, imageReplacements, setImageReplacements, stylePrompt, pdfImages } = useContext(DataContext);
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [picker, setPicker] = useState(null); // { slideIndex, shapeId } | null
    const [generatedSlides, setGeneratedSlides] = useState([]);
    const [pptxDownloadUrl, setPptxDownloadUrl] = useState(null);
    const [pdfDownloadUrl, setPdfDownloadUrl] = useState(null);

    //Helper function to create downloadable urls
    function b64toBlob(b64, mime) {
        const bytes = atob(b64);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        return new Blob([arr], { type: mime });
    }

    //function to generate the actual slides
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

    function selectPdfImage(img) {
        const mime = `image/${img.ext}`;
        const bytes = atob(img.base64);
        const arr = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
        const file = new File([new Blob([arr], { type: mime })], `doc_img_${img.xref}.${img.ext}`, { type: mime });
        handleReplace(picker.slideIndex, picker.shapeId, file);
        setPicker(null);
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
        <>
        <div className="flex flex-row h-screen w-full bg-surface">
            <div className='flex flex-col flex-[0_0_30%] h-screen px-5 py-6 overflow-y-auto text-secondary bg-surface border-r border-border box-border items-center'>

                {/**----Back Button to Home Page----  */}
                <button className='flex items-center justify-center bg-transparent border-0 text-primary cursor-pointer self-start mb-4 p-0 opacity-80 transition-opacity duration-150 hover:opacity-100' onClick={() => navigate('/')}>
                    <IoCaretBack size={32} />
                    Back
                </button>

                {/**----  Header for the application name----*/}
                <div className='text-center'>
                    <div className='flex flex-row items-center gap-[10px] ml-[10px] mb-[10px]'>
                        <HiPresentationChartBar size={32} style={{ color: "var(--color-primary)" }} />
                        <h1 className='text-[1.4rem] font-normal text-secondary mt-0 mb-[2px]'>Turn Any Document into a Presentation</h1>
                    </div>
                    <p className='text-[0.8rem] text-muted m-0'>Before we generate your presentation, feel free to replace images on any slide.</p>
                </div>

                {/**----  Display All Provided Information ---- */}
                <div className='flex flex-row bg-surface border border-primary rounded-[10px] m-[10px] px-5 py-[10px] w-[350px] items-center gap-[10px]'>
                    <FaFilePdf size={32} style={{ color: "var(--color-primary)", marginTop: "20px" }} />
                    <div>{pdfFile ? pdfFile.name : 'No file uploaded'}</div>
                </div>
                <div className='flex flex-row bg-surface border border-primary rounded-[10px] m-[10px] px-5 py-[10px] w-[350px] items-center gap-[10px]'>
                    <FaFilePowerpoint size={32} style={{ color: "var(--color-primary)", marginTop: "20px" }} />
                    <div>{pptxFile ? pptxFile.name : 'No template uploaded'}</div>
                </div>

                <div className='flex flex-col gap-[10px] m-[10px]'>
                    <h1 className='text-[1.1rem] text-primary ml-3'> Prompt: </h1>
                    <div className='flex flex-row bg-surface border border-primary rounded-[10px] m-[10px] px-5 py-[10px] w-[350px] items-center gap-[10px] italic'>
                        <div>{stylePrompt || 'No prompt provided'}</div>
                    </div>
                </div>

                {/** ---- image replacement ---- */}
                {totalReplacements > 0 && (
                    <div className='flex items-center gap-2 bg-primary-muted border border-primary rounded-lg px-[14px] py-2 m-[10px] text-[0.85rem] text-primary font-medium w-[322px]'>
                        <FaImage size={16} style={{ color: "var(--color-danger)" }} />
                        <span>{totalReplacements} image{totalReplacements > 1 ? 's' : ''} queued for replacement</span>
                    </div>
                )}

                <p className='text-[0.78rem] text-subtle text-center px-3 leading-[1.5] mt-3'>
                    Hover over highlighted regions on any slide to replace its image. Slides without images are shown for reference only.
                </p>

                <button onClick={handleGenerate} disabled={loading} className='mt-4 px-[30px] py-3 bg-primary text-white border-2 border-primary rounded-lg cursor-pointer text-base w-[350px] hover:bg-white hover:text-primary disabled:opacity-60 disabled:cursor-not-allowed'>
                    {loading ? 'Generating…' : 'Generate'}
                </button>

                {error && <p className='text-red-500 text-[0.82rem] text-center mt-2'>{error}</p>}

                {pptxDownloadUrl && (
                    <a href={pptxDownloadUrl} download="presentation.pptx" className='block text-center mt-[10px] text-primary text-[0.9rem] font-semibold underline'>
                        ⬇ Download PPTX
                    </a>
                )}
                {pdfDownloadUrl && (
                    <a href={pdfDownloadUrl} download="presentation.pdf" className='block text-center mt-[10px] text-primary text-[0.9rem] font-semibold underline'>
                        ⬇ Download PDF
                    </a>
                )}
            </div>

            {/**----  Display Slide Template and Generated Slides---- */}
            <div className='flex-[0_0_70%] h-screen overflow-y-auto bg-canvas box-border p-6'>
                {generatedSlides.length > 0 ? (
                    <div className='flex flex-col gap-6'>
                        {generatedSlides.map((slide) => (
                            <div key={slide.slide_index} className='bg-white rounded-[10px] overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.15)]'>
                                <div className='text-[0.75rem] font-semibold text-secondary px-[10px] py-[6px] bg-slide-label border-b border-border'>Slide {slide.slide_index + 1}</div>
                                <div className='relative w-full leading-[0]'>
                                    <img
                                        src={slide.thumbnail}
                                        alt={`Slide ${slide.slide_index + 1}`}
                                        className='w-full block'
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : templateImages ? (
                    <div className='flex flex-col gap-6'>
                        {templateImages.map((slide) => (
                            <div key={slide.slide_key} className='bg-white rounded-[10px] overflow-hidden shadow-[0_2px_8px_rgba(0,0,0,0.15)]'>
                                <div className='text-[0.75rem] font-semibold text-secondary px-[10px] py-[6px] bg-slide-label border-b border-border'>Slide {slide.slide_index + 1}</div>
                                <div className='relative w-full leading-[0]'>
                                    <img
                                        src={slide.thumbnail}
                                        alt={`Slide ${slide.slide_index + 1}`}
                                        className='w-full block'
                                    />
                                    {slide.images.map((img) => {
                                        const key = `${slide.slide_index}_${img.shape_id}`;
                                        const replacement = imageReplacements[key];
                                        return (
                                            <div
                                                key={img.shape_id}
                                                className={`absolute box-border flex items-center justify-center cursor-pointer transition-colors duration-150 group ${
                                                    replacement
                                                        ? 'border-4 border-success bg-transparent'
                                                        : 'border-4 border-dashed border-danger bg-[rgba(229,57,53,0.08)] hover:bg-[rgba(229,57,53,0.18)]'
                                                }`}
                                                style={{
                                                    left: `${img.left_pct * 100}%`,
                                                    top: `${img.top_pct * 100}%`,
                                                    width: `${img.width_pct * 100}%`,
                                                    height: `${img.height_pct * 100}%`,
                                                }}
                                            >
                                                {replacement ? (
                                                    <div className='relative w-full h-full'>
                                                        <img
                                                            src={URL.createObjectURL(replacement.file)}
                                                            alt="replacement"
                                                            className='w-full h-full object-cover block rounded-[2px]'
                                                        />
                                                        <button
                                                            className='absolute top-[3px] right-[3px] w-5 h-5 rounded-full border-0 bg-[rgba(0,0,0,0.55)] text-white text-[0.85rem] leading-[1] cursor-pointer flex items-center justify-center opacity-0 transition-opacity duration-150 group-hover:opacity-100'
                                                            onClick={() => handleRemove(slide.slide_index, img.shape_id)}
                                                            title="Remove replacement"
                                                        >×</button>
                                                    </div>
                                                ) : (
                                                    <div
                                                        className='flex flex-col items-center justify-center gap-1 text-danger text-[0.7rem] font-semibold cursor-pointer w-full h-full opacity-0 transition-opacity duration-150 group-hover:opacity-100'
                                                        onClick={() => setPicker({ slideIndex: slide.slide_index, shapeId: img.shape_id })}
                                                    >
                                                        <FaImage size={52} />
                                                        <div className='text-[18px]'>Replace</div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className='text-subtle text-[0.95rem] text-center mt-10'>No template selected — upload a PPTX on the home page first.</p>
                )}
            </div>
        </div>

        {picker && (
            <div className='fixed inset-0 bg-[rgba(0,0,0,0.45)] flex items-center justify-center z-[1000]' onClick={() => setPicker(null)}>
                <div className='bg-white rounded-[12px] w-[480px] max-h-[80vh] overflow-y-auto shadow-[0_8px_32px_rgba(0,0,0,0.22)] flex flex-col' onClick={e => e.stopPropagation()}>
                    <div className='flex items-center justify-between px-5 pt-4 pb-3 border-b border-border-soft text-base font-semibold text-secondary'>
                        <span>Choose an image</span>
                        <button className='bg-transparent border-0 text-[1.4rem] leading-[1] cursor-pointer text-subtle px-1 hover:text-[#333]' onClick={() => setPicker(null)}>×</button>
                    </div>

                    {pdfImages && pdfImages.length > 0 && (
                        <div className='px-5 py-[14px]'>
                            <div className='text-[0.7rem] font-bold uppercase tracking-[0.06em] text-faint mb-[10px]'>From document</div>
                            <div className='grid grid-cols-3 gap-2'>
                                {pdfImages.map(img => (
                                    <img
                                        key={img.xref}
                                        src={`data:image/${img.ext};base64,${img.base64}`}
                                        className='w-full aspect-[4/3] object-cover rounded-md cursor-pointer border-2 border-transparent transition-[border-color,transform] duration-150 hover:border-primary hover:scale-[1.03]'
                                        alt={`doc image ${img.xref}`}
                                        onClick={() => selectPdfImage(img)}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    <div className={`px-5 py-[14px]${pdfImages && pdfImages.length > 0 ? ' border-t border-border-soft' : ''}`}>
                        <div className='text-[0.7rem] font-bold uppercase tracking-[0.06em] text-faint mb-[10px]'>Upload your own</div>
                        <label className='inline-block px-[18px] py-2 bg-primary text-white rounded-md text-[0.85rem] font-medium cursor-pointer transition-colors duration-150 hover:bg-secondary'>
                            <input
                                type="file"
                                accept="image/*"
                                className='hidden'
                                onChange={e => {
                                    if (e.target.files[0]) {
                                        handleReplace(picker.slideIndex, picker.shapeId, e.target.files[0]);
                                        setPicker(null);
                                    }
                                }}
                            />
                            Choose file…
                        </label>
                    </div>
                </div>
            </div>
        )}
        </>
    );
}

export default Powerpoint;
