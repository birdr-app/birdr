import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Keyboard,
  Platform,
} from 'react-native';
import { ensureSoftwareKeyboardShown } from '../../modules/software-keyboard';
import { colors } from '../theme';

export type ExpertSpeciesOption = { id: string; title: string };

type Props = {
  dataSet: ExpertSpeciesOption[];
  onSelect: (item: ExpertSpeciesOption) => void;
  loading?: boolean;
  minChars?: number;
  editable?: boolean;
  placeholder: string;
  emptyResultText: string;
  testID?: string;
  accessibilityLabel?: string;
};

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function ExpertSpeciesInput({
  dataSet,
  onSelect,
  loading = false,
  minChars = 2,
  editable = true,
  placeholder,
  emptyResultText,
  testID,
  accessibilityLabel,
}: Props) {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<TextInput>(null);
  const keyboardVisibleRef = useRef(false);
  const showKeyboardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const shown = Keyboard.addListener('keyboardDidShow', () => {
      keyboardVisibleRef.current = true;
    });
    const hidden = Keyboard.addListener('keyboardDidHide', () => {
      keyboardVisibleRef.current = false;
    });
    return () => {
      shown.remove();
      hidden.remove();
      if (showKeyboardTimer.current) clearTimeout(showKeyboardTimer.current);
    };
  }, []);

  const requestSoftwareKeyboard = () => {
    if (!(Platform.OS === 'ios' && Platform.isPad)) return;
    if (showKeyboardTimer.current) clearTimeout(showKeyboardTimer.current);
    showKeyboardTimer.current = setTimeout(() => {
      if (!keyboardVisibleRef.current) {
        ensureSoftwareKeyboardShown();
      }
    }, 450);
  };

  const matches = useMemo(() => {
    const q = normalize(query.trim());
    if (q.length < minChars) return [];
    return dataSet.filter((item) => normalize(item.title).includes(q)).slice(0, 40);
  }, [dataSet, minChars, query]);

  const showList = focused && query.trim().length >= minChars && !loading;

  return (
    <View style={styles.wrap}>
      <TextInput
        ref={inputRef}
        value={query}
        onChangeText={setQuery}
        onFocus={() => {
          setFocused(true);
          requestSoftwareKeyboard();
        }}
        onPressIn={() => {
          requestSoftwareKeyboard();
        }}
        onBlur={() => {
          setTimeout(() => setFocused(false), 150);
        }}
        editable={editable}
        placeholder={placeholder}
        placeholderTextColor={colors.primary[500]}
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="off"
        spellCheck={false}
        showSoftInputOnFocus
        keyboardType={Platform.OS === 'ios' && Platform.isPad ? 'ascii-capable' : 'default'}
        inputMode="text"
        enterKeyHint="search"
        returnKeyType="search"
        blurOnSubmit={false}
        importantForAutofill="no"
        testID={testID}
        accessibilityLabel={accessibilityLabel}
        style={styles.input}
      />
      {loading ? (
        <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loader} />
      ) : null}
      {showList ? (
        // Opens above the input so the on-screen keyboard doesn't cover it.
        <ScrollView
          style={styles.list}
          keyboardShouldPersistTaps="always"
          nestedScrollEnabled
        >
          {matches.length === 0 ? (
            <Text style={styles.empty}>{emptyResultText}</Text>
          ) : (
            matches.map((item) => (
              <TouchableOpacity
                key={item.id}
                style={styles.item}
                onPress={() => {
                  Keyboard.dismiss();
                  setQuery('');
                  setFocused(false);
                  onSelect(item);
                }}
              >
                <Text style={styles.itemText}>{item.title}</Text>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 8, zIndex: 10 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 12,
    fontSize: 16,
    color: colors.primary[800],
    backgroundColor: colors.primary[50],
    minHeight: 48,
  },
  loader: { marginTop: 8 },
  list: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: '100%',
    maxHeight: 240,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    backgroundColor: '#fff',
    elevation: 6,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: -2 },
  },
  item: {
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  itemText: { fontSize: 16, color: colors.primary[800] },
  empty: { fontSize: 14, color: colors.primary[500], paddingVertical: 16, paddingHorizontal: 12 },
});
