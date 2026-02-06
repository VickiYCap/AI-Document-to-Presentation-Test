import { createContext } from "react";
export const DataContext = createContext({
    paredData: null,
    setParsedData: () => {},
});