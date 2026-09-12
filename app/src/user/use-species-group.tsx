import {useContext, useEffect, useState} from "react";
import AppContext from "../core/app-context"
import { apiUrl } from "../api/baseUrl"

export interface SpeciesGroup {
  species_group: string
  name_en: string
  name_nl: string
  name_es?: string
  name_fr?: string
  name_de?: string
  name_it?: string
  name_pt_br?: string
  name_ja?: string
  count: number
}

export const UseSpeciesGroup = () => {
  const [speciesGroups, setSpeciesGroups] = useState<SpeciesGroup[]>([])
  const {country} = useContext(AppContext);

  useEffect(() => {
      const fetchSpeciesGroups = async () => {
        setSpeciesGroups([])
        try {
          const url: string = country ? apiUrl(`/api/groups/?country=${country.code}`) : apiUrl('/api/groups/');
          const response: Response = await fetch(url);
          const data: any = await response.json();

          if (Array.isArray(data)) {
            setSpeciesGroups(data);
          } else {
            console.error('Unexpected response format:', data);
            setSpeciesGroups([]);
          }
        } catch (error) {
          console.error('Error fetching species groups:', error);
          setSpeciesGroups([]);
        }
      };

      fetchSpeciesGroups();
  }, [country?.code])

  return {
    speciesGroups,
  }
}
