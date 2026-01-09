import React, { ReactNode } from 'react';

type WebLayoutProps = {
  children: ReactNode;
  showBottomTabs?: boolean;
  bottomTabs?: ReactNode;
};

const FOOTER_HEIGHT = 72;

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    width: '100vw',
    backgroundColor: 'var(--background-color, #fff)',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    overflowX: 'hidden',
    WebkitOverflowScrolling: 'touch',
  },
  scrollViewport: {
    minHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
  },
  footer: {
    flexShrink: 0,
    height: FOOTER_HEIGHT,
    width: '100%',
    borderTop: '1px solid rgba(0, 0, 0, 0.08)',
    backgroundColor: 'var(--surface-color, #fff)',
    display: 'flex',
    flexDirection: 'column',
  },
  footerContent: {
    flex: 1,
    width: '100%',
    height: '100%',
    display: 'flex',
  },
};

export default function WebLayout({
  children,
  showBottomTabs,
  bottomTabs,
}: WebLayoutProps) {
  return (
    <div style={styles.root}>
      <div style={styles.content}>
        <div style={styles.scrollViewport}>{children}</div>
      </div>
      {showBottomTabs && bottomTabs ? (
        <div style={styles.footer}>
          <div style={styles.footerContent}>{bottomTabs}</div>
        </div>
      ) : null}
    </div>
  );
}

