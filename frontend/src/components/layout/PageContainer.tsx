import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  wide?: boolean;
}

export default function PageContainer({ children, wide }: PageContainerProps) {
  return (
    <div className={`mx-auto w-full px-6 py-6 ${wide ? 'max-w-[1440px]' : 'max-w-4xl'}`}>
      {children}
    </div>
  );
}
