import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { IconInfo } from './Icons.jsx';

export default function TermTooltip({ text, position = 'top', pos }) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState(null);
  const triggerRef = useRef(null);

  const preferredPos = pos || position || 'top';

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    // Responsive width: max 240px, or narrower on small screens
    const tooltipWidth = Math.min(240, Math.max(160, window.innerWidth - 32));
    const gap = 8;
    const margin = 12; // Safety margin from screen edge

    // Automatic vertical flipping to prevent cutting by navbar, headers, or window edges
    // The top navbar is sticky (~65px). If rect.top < 140, always flip to 'bottom'
    // If rect.bottom > window.innerHeight - 130, always flip to 'top'
    let resolvedPos = preferredPos;
    if (rect.top < 140) {
      resolvedPos = 'bottom';
    } else if (window.innerHeight - rect.bottom < 130) {
      resolvedPos = 'top';
    }

    let top = 0;
    if (resolvedPos === 'top') {
      top = rect.top - gap;
    } else {
      top = rect.bottom + gap;
    }

    // Horizontal centering & strict window boundary clamping
    const triggerCenter = rect.left + rect.width / 2;
    let left = triggerCenter - tooltipWidth / 2;

    // Strict boundary clamping: 100% prevents horizontal scrollbars and edge clipping!
    const minLeft = margin;
    const maxLeft = window.innerWidth - tooltipWidth - margin;
    left = Math.max(minLeft, Math.min(left, maxLeft));

    // Arrow pointer position relative to the tooltip bubble
    const arrowLeft = Math.max(14, Math.min(triggerCenter - left, tooltipWidth - 14));

    setCoords({
      top,
      left,
      pos: resolvedPos,
      arrowLeft,
      width: tooltipWidth,
    });
  }, [preferredPos]);

  useEffect(() => {
    if (!visible) return;
    updatePosition();

    const handleScrollOrResize = () => {
      updatePosition();
    };

    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);

    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [visible, updatePosition]);

  if (!text) return null;

  return (
    <>
      <span
        ref={triggerRef}
        className="term-tooltip-trigger"
        onMouseEnter={() => {
          updatePosition();
          setVisible(true);
        }}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => {
          updatePosition();
          setVisible(true);
        }}
        onBlur={() => setVisible(false)}
        tabIndex="0"
        aria-label={text}
        role="note"
      >
        <IconInfo size={12} className="tooltip-icon" />
      </span>

      {visible && coords && createPortal(
        <div
          className={`term-tooltip-portal-bubble pos-${coords.pos}`}
          style={{
            ...(coords.pos === 'top'
              ? { bottom: `${window.innerHeight - coords.top}px` }
              : { top: `${coords.top}px` }),
            left: `${coords.left}px`,
            width: `${coords.width}px`,
          }}
        >
          {text}
          <div
            className="tooltip-bubble-arrow"
            style={{
              left: `${coords.arrowLeft}px`,
            }}
          />
        </div>,
        document.body
      )}
    </>
  );
}
