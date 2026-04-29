import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { findTurnVirtualRangeIndex } from './historyUtils';
import {
  TURN_VIRTUALIZATION_ESTIMATED_HEIGHT,
  TURN_VIRTUALIZATION_OVERSCAN,
} from './types';
import type { ConversationHealth, MessageTurn } from './types';
import type { ConversationType } from '../../types/conversation';

interface UseTurnVirtualizationOptions {
  messageTurns: MessageTurn[];
  shouldVirtualizeTurns: boolean;
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  currentConversationId: string | null;
  currentConversationType?: ConversationType;
  canJumpBackToLatest: boolean;
  currentConversationHealth: ConversationHealth | null;
  hasMoreBefore?: boolean;
  onNearBottomChange: (isNearBottom: boolean) => void;
}

export const useTurnVirtualization = ({
  messageTurns,
  shouldVirtualizeTurns,
  scrollContainerRef,
  currentConversationId,
  currentConversationType,
  canJumpBackToLatest,
  currentConversationHealth,
  hasMoreBefore,
  onNearBottomChange,
}: UseTurnVirtualizationOptions) => {
  const [turnViewportState, setTurnViewportState] = useState({ scrollTop: 0, height: 0 });
  const [turnListOffsetTop, setTurnListOffsetTop] = useState(0);
  const [turnHeightVersion, setTurnHeightVersion] = useState(0);
  const turnListContainerRef = useRef<HTMLDivElement>(null);
  const virtualizedTurnHeightsRef = useRef<Record<string, number>>({});
  const virtualizedTurnElementsRef = useRef(new Map<string, HTMLDivElement>());
  const virtualizedTurnResizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    let frameId: number | null = null;
    const updateScrollState = () => {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      onNearBottomChange(distanceFromBottom < 120);
      setTurnViewportState((prev) => (
        prev.scrollTop === container.scrollTop && prev.height === container.clientHeight
          ? prev
          : { scrollTop: container.scrollTop, height: container.clientHeight }
      ));
    };

    const scheduleUpdateScrollState = () => {
      if (frameId !== null) {
        return;
      }
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        updateScrollState();
      });
    };

    updateScrollState();
    container.addEventListener('scroll', scheduleUpdateScrollState, { passive: true });

    const resizeObserver = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(() => scheduleUpdateScrollState())
      : null;
    resizeObserver?.observe(container);

    return () => {
      container.removeEventListener('scroll', scheduleUpdateScrollState);
      resizeObserver?.disconnect();
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [currentConversationId, onNearBottomChange, scrollContainerRef]);

  useLayoutEffect(() => {
    const nextOffsetTop = turnListContainerRef.current?.offsetTop || 0;
    setTurnListOffsetTop((prev) => (prev === nextOffsetTop ? prev : nextOffsetTop));
  }, [
    canJumpBackToLatest,
    currentConversationHealth,
    currentConversationId,
    currentConversationType,
    hasMoreBefore,
    messageTurns.length,
  ]);

  const turnVirtualizationMetrics = useMemo(() => {
    const rowHeights = messageTurns.map((turn) => (
      virtualizedTurnHeightsRef.current[turn.id] || TURN_VIRTUALIZATION_ESTIMATED_HEIGHT
    ));
    const rowOffsets: number[] = new Array(messageTurns.length);
    let currentOffset = 0;

    rowHeights.forEach((height, index) => {
      rowOffsets[index] = currentOffset;
      currentOffset += height;
    });

    return {
      rowHeights,
      rowOffsets,
      totalHeight: currentOffset,
    };
  }, [messageTurns, turnHeightVersion]);

  const visibleVirtualizedTurnIndexes = useMemo(() => {
    if (!shouldVirtualizeTurns || messageTurns.length === 0) {
      return messageTurns.map((_, index) => index);
    }

    const viewportTop = Math.max(0, turnViewportState.scrollTop - turnListOffsetTop);
    const viewportBottom = viewportTop + Math.max(1, turnViewportState.height);
    const { rowHeights, rowOffsets } = turnVirtualizationMetrics;
    const maxOffset = Math.max(0, turnVirtualizationMetrics.totalHeight - 1);
    const startIndex = Math.max(
      0,
      findTurnVirtualRangeIndex(rowOffsets, Math.min(viewportTop, maxOffset)) - TURN_VIRTUALIZATION_OVERSCAN,
    );

    let stopIndex = findTurnVirtualRangeIndex(rowOffsets, Math.min(viewportBottom, maxOffset));
    while (
      stopIndex < rowHeights.length - 1
      && rowOffsets[stopIndex] + rowHeights[stopIndex] < viewportBottom
    ) {
      stopIndex += 1;
    }
    stopIndex = Math.min(rowHeights.length - 1, stopIndex + TURN_VIRTUALIZATION_OVERSCAN);

    const indexes: number[] = [];
    for (let index = startIndex; index <= stopIndex; index += 1) {
      indexes.push(index);
    }
    return indexes;
  }, [messageTurns, shouldVirtualizeTurns, turnListOffsetTop, turnViewportState, turnVirtualizationMetrics]);

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      let hasHeightChange = false;
      entries.forEach((entry) => {
        const element = entry.target as HTMLDivElement;
        const turnId = element.dataset.turnId;
        if (!turnId) {
          return;
        }
        const nextHeight = Math.ceil(element.getBoundingClientRect().height);
        if (!nextHeight || virtualizedTurnHeightsRef.current[turnId] === nextHeight) {
          return;
        }
        virtualizedTurnHeightsRef.current[turnId] = nextHeight;
        hasHeightChange = true;
      });

      if (hasHeightChange) {
        setTurnHeightVersion((prev) => prev + 1);
      }
    });

    virtualizedTurnResizeObserverRef.current = observer;
    virtualizedTurnElementsRef.current.forEach((element) => observer.observe(element));

    return () => {
      if (virtualizedTurnResizeObserverRef.current === observer) {
        virtualizedTurnResizeObserverRef.current = null;
      }
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const activeTurnIds = new Set(messageTurns.map((turn) => turn.id));
    let removedHeight = false;

    Object.keys(virtualizedTurnHeightsRef.current).forEach((turnId) => {
      if (activeTurnIds.has(turnId)) {
        return;
      }
      delete virtualizedTurnHeightsRef.current[turnId];
      removedHeight = true;
    });

    virtualizedTurnElementsRef.current.forEach((element, turnId) => {
      if (activeTurnIds.has(turnId)) {
        return;
      }
      virtualizedTurnResizeObserverRef.current?.unobserve(element);
      virtualizedTurnElementsRef.current.delete(turnId);
    });

    if (removedHeight) {
      setTurnHeightVersion((prev) => prev + 1);
    }
  }, [messageTurns]);

  const registerVirtualizedTurnElement = useCallback((turnId: string, element: HTMLDivElement | null) => {
    const existingElement = virtualizedTurnElementsRef.current.get(turnId);
    if (existingElement === element) {
      return;
    }

    if (existingElement) {
      virtualizedTurnResizeObserverRef.current?.unobserve(existingElement);
      virtualizedTurnElementsRef.current.delete(turnId);
    }

    if (!element) {
      return;
    }

    virtualizedTurnElementsRef.current.set(turnId, element);
    virtualizedTurnResizeObserverRef.current?.observe(element);

    const nextHeight = Math.ceil(element.getBoundingClientRect().height);
    if (nextHeight && virtualizedTurnHeightsRef.current[turnId] !== nextHeight) {
      virtualizedTurnHeightsRef.current[turnId] = nextHeight;
      setTurnHeightVersion((prev) => prev + 1);
    }
  }, []);

  const cleanupTurnVirtualization = useCallback(() => {
    virtualizedTurnResizeObserverRef.current?.disconnect();
    virtualizedTurnResizeObserverRef.current = null;
    virtualizedTurnElementsRef.current.clear();
  }, []);

  return {
    turnListContainerRef,
    turnHeightVersion,
    turnVirtualizationMetrics,
    visibleVirtualizedTurnIndexes,
    registerVirtualizedTurnElement,
    cleanupTurnVirtualization,
  };
};
