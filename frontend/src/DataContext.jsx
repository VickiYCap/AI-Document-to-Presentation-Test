import { createContext } from "react";
export const DataContext = createContext({
    templateImages: null,
    setTemplateImages: () => {},
    imageReplacements: {},
    setImageReplacements: () => {},
    pdfFile: null,
    setPdfFile: () => {},
    pptxFile: null,
    setPptxFile: () => {},
    stylePrompt: '',
    setStylePrompt: () => {},
});
