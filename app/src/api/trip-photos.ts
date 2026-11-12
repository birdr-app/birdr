import axios from './axios-config';
import { getApiBaseUrl } from './baseUrl';
import type { CandidatePhoto, PhotoPick } from './course-photos';

/** Admin API for choosing the photos of a trip prep pack (staff only). */

export type TripPhotoBird = {
  species_id: number;
  code: string;
  name: string;
  name_nl: string;
  latin: string;
  file: { card: number[]; quiz: number[] };
  pick: PhotoPick | null;
};

export type TripPhotoSection = { slug: string; title: string; birds: TripPhotoBird[] };

export type TripPhotos = {
  trip: string;
  name: string;
  trips: { code: string; name: string; parent: string | null }[];
  sections: TripPhotoSection[];
};

const base = (trip: string) => `${getApiBaseUrl()}/api/trips/${trip}/photos`;

export async function fetchTripPhotos(trip: string): Promise<TripPhotos> {
  const res = await axios.get<TripPhotos>(`${base(trip)}/`);
  return res.data;
}

export function tripPhotoApi(trip: string) {
  return {
    fetchPhotos: async (speciesId: number): Promise<CandidatePhoto[]> =>
      (await axios.get<{ media: CandidatePhoto[] }>(`${base(trip)}/species/${speciesId}/`)).data.media,
    addCommons: async (speciesId: number, link: string): Promise<CandidatePhoto> => {
      try {
        return (await axios.post<{ photo: CandidatePhoto }>(`${base(trip)}/species/${speciesId}/commons/`, { link })).data.photo;
      } catch (error: any) {
        throw new Error(error?.response?.data?.error || 'The photo could not be added.');
      }
    },
    save: async (speciesId: number, pick: PhotoPick): Promise<PhotoPick> =>
      (await axios.put<PhotoPick>(`${base(trip)}/${speciesId}/`, pick)).data,
  };
}
