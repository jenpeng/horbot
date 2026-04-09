import api from './api';

export interface SoulData {
  name: string;
  content: string;
  error?: string;
}

const soulService = {
  getSoul: async (): Promise<SoulData> => {
    try {
      const response = await api.get<SoulData>('/api/soul');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch soul data:', error);
      return { name: 'horbot', content: '' };
    }
  },
};

export default soulService;
