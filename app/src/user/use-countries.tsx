import {useEffect, useState} from "react";
import { apiUrl } from "../api/baseUrl"

export interface Country {
  code: string
  name: string
  parent?: string | null
  kind?: string
  hemisphere?: string
}

export const UseCountries = () => {
  const [countries, setCountries] = useState<Country[]>([])
  useEffect(() => {
    if (countries.length === 0) {
      const fetchCountries = async () => {
        try {
          const response: Response = await fetch(apiUrl('/api/countries/'));
          const data: any = await response.json();
          
          if (Array.isArray(data)) {
            setCountries(data);
          } else {
            console.error('Unexpected response format:', data);
            setCountries([]);
          }
        } catch (error) {
          console.error('Error fetching countries:', error);
          setCountries([]);
        }
      };
      
      fetchCountries();
    }
  }, []) // Only run once on mount


  return {
    countries,
  }
}

