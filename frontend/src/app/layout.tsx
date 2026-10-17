import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'Faultline | Incident intelligence',description:'Investigate deploys, changes and production incidents with evidence instead of guesswork'};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en"><body>{children}</body></html>}
