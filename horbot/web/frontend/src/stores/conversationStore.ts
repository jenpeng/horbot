import { create } from 'zustand';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { Conversation, Message } from '../types/conversation';
import {
  ConversationType,
  createDMConversationId,
  createTeamConversationId,
} from '../types/conversation';

const CONVERSATION_STORAGE_KEY = 'horbot-conversations';

const conversationStorageBackend: StateStorage = {
  getItem: (name: string): string | null => {
    if (typeof window === 'undefined') {
      return null;
    }
    return window.localStorage.getItem(name);
  },
  setItem: (name: string, value: string): void => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(name, value);
  },
  removeItem: (name: string): void => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.removeItem(name);
  },
};

const conversationStorage = createJSONStorage(() => conversationStorageBackend);

export interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Record<string, Message[]>;
  typingAgents: Record<string, string[]>;
  
  setCurrentConversation: (convId: string | null) => void;
  getOrCreateDMConversation: (agentId: string, agentName: string) => Conversation;
  getOrCreateTeamConversation: (
    teamId: string,
    teamName: string,
    memberIds: string[],
    description?: string
  ) => Conversation;
  addMessage: (convId: string, message: Message) => void;
  updateMessage: (convId: string, messageId: string, updates: Partial<Message>) => void;
  setMessages: (convId: string, messages: Message[]) => void;
  addTypingAgent: (convId: string, agentId: string) => void;
  removeTypingAgent: (convId: string, agentId: string) => void;
  getTypingAgents: (convId: string) => string[];
  getCurrentConversation: () => Conversation | null;
  getMessages: (convId: string) => Message[];
}

export const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      messages: {},
      typingAgents: {},
      
      setCurrentConversation: (convId) => {
        set({ currentConversationId: convId });
      },
      
      getOrCreateDMConversation: (agentId, agentName) => {
        const convId = createDMConversationId(agentId);
        const existing = get().conversations.find(c => c.id === convId);
        if (existing) return existing;
        
        const newConv: Conversation = {
          id: convId,
          type: ConversationType.DM,
          targetId: agentId,
          name: agentName,
          agentIds: [agentId],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        
        set(state => ({
          conversations: [...state.conversations, newConv],
        }));
        
        return newConv;
      },
      
      getOrCreateTeamConversation: (teamId, teamName, memberIds, description) => {
        const convId = createTeamConversationId(teamId);
        const existing = get().conversations.find(c => c.id === convId);
        if (existing) return existing;
        
        const newConv: Conversation = {
          id: convId,
          type: ConversationType.TEAM,
          targetId: teamId,
          name: teamName,
          description,
          agentIds: memberIds,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        
        set(state => ({
          conversations: [...state.conversations, newConv],
        }));
        
        return newConv;
      },
      
      addMessage: (convId, message) => {
        set(state => {
          const existingMessages = state.messages[convId] || [];
          return {
            messages: {
              ...state.messages,
              [convId]: [...existingMessages, message],
            },
          };
        });
      },
      
      updateMessage: (convId, messageId, updates) => {
        set(state => {
          const messages = state.messages[convId] || [];
          return {
            messages: {
              ...state.messages,
              [convId]: messages.map(m =>
                m.id === messageId ? { ...m, ...updates } : m
              ),
            },
          };
        });
      },
      
      setMessages: (convId, messages) => {
        set(state => ({
          messages: {
            ...state.messages,
            [convId]: messages,
          },
        }));
      },
      
      addTypingAgent: (convId, agentId) => {
        set(state => {
          const typing = state.typingAgents[convId] || [];
          if (typing.includes(agentId)) return state;
          return {
            typingAgents: {
              ...state.typingAgents,
              [convId]: [...typing, agentId],
            },
          };
        });
      },
      
      removeTypingAgent: (convId, agentId) => {
        set(state => {
          const typing = state.typingAgents[convId] || [];
          return {
            typingAgents: {
              ...state.typingAgents,
              [convId]: typing.filter(id => id !== agentId),
            },
          };
        });
      },
      
      getTypingAgents: (convId) => {
        return get().typingAgents[convId] || [];
      },
      
      getCurrentConversation: () => {
        const { currentConversationId, conversations } = get();
        if (!currentConversationId) return null;
        return conversations.find(c => c.id === currentConversationId) || null;
      },
      
      getMessages: (convId) => {
        return get().messages[convId] || [];
      },
    }),
    {
      name: CONVERSATION_STORAGE_KEY,
      storage: conversationStorage,
      partialize: (state) => ({
        conversations: state.conversations,
        currentConversationId: state.currentConversationId,
      }) as any,
    }
  )
);
