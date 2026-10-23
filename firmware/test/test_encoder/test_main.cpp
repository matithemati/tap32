// Testy dekodera enkodera: sekwencje A/B, drgania styków, przeliczanie na ząbki.
#include <unity.h>

#include "quad_decoder.h"

using tap32::DetentCounter;
using tap32::QuadDecoder;

namespace {

struct AB {
  uint8_t a;
  uint8_t b;
};

// Pełny cykl CW: 11 → 10 → 00 → 01 → 11 (spoczynek EC11 = 11).
const AB kCwCycle[] = {{1, 0}, {0, 0}, {0, 1}, {1, 1}};
const AB kCcwCycle[] = {{0, 1}, {0, 0}, {1, 0}, {1, 1}};

int32_t feedAll(QuadDecoder& dec, const AB* seq, int n) {
  int32_t sum = 0;
  for (int i = 0; i < n; ++i) sum += dec.update(seq[i].a, seq[i].b);
  return sum;
}

}  // namespace

void setUp() {}
void tearDown() {}

void test_full_cycle_cw_gives_four_pulses() {
  QuadDecoder dec;
  dec.reset(1, 1);
  TEST_ASSERT_EQUAL_INT32(4, feedAll(dec, kCwCycle, 4));
  TEST_ASSERT_EQUAL_UINT8(3, dec.state());
}

void test_full_cycle_ccw_gives_minus_four() {
  QuadDecoder dec;
  dec.reset(1, 1);
  TEST_ASSERT_EQUAL_INT32(-4, feedAll(dec, kCcwCycle, 4));
}

void test_bounce_cancels_out() {
  QuadDecoder dec;
  dec.reset(1, 1);
  // Drgania A na pierwszym zboczu: 11→10→11→10→11→10, potem dalej normalnie.
  const AB seq[] = {{1, 0}, {1, 1}, {1, 0}, {1, 1}, {1, 0}, {0, 0}, {0, 1}, {0, 0},
                    {0, 1}, {1, 1}};
  TEST_ASSERT_EQUAL_INT32(4, feedAll(dec, seq, 10));
}

void test_invalid_transition_is_ignored() {
  QuadDecoder dec;
  dec.reset(1, 1);
  // Skok 11 → 00 (zgubione przerwanie) nie liczy się w żadną stronę.
  TEST_ASSERT_EQUAL_INT8(0, dec.update(0, 0));
  TEST_ASSERT_EQUAL_INT8(0, dec.update(0, 0));  // brak zmiany
}

void test_detents_four_pulses() {
  DetentCounter dc;
  dc.setPulsesPerDetent(4);
  TEST_ASSERT_EQUAL_INT32(0, dc.feed(3, 0));
  TEST_ASSERT_EQUAL_INT32(1, dc.feed(1, 3));
  TEST_ASSERT_EQUAL_INT32(2, dc.feed(8, 3));
  TEST_ASSERT_EQUAL_INT32(-1, dc.feed(-4, 3));
}

void test_detents_resync_at_rest() {
  DetentCounter dc;
  dc.setPulsesPerDetent(4);
  // Zgubiony jeden impuls: 3 impulsy, ale enkoder już w spoczynku → zaokrąglenie do 1 ząbka.
  TEST_ASSERT_EQUAL_INT32(1, dc.feed(3, 3));
  // Drganie przy spoczynku (+1 i powrót) nie daje kroku.
  TEST_ASSERT_EQUAL_INT32(0, dc.feed(1, 2));
  TEST_ASSERT_EQUAL_INT32(0, dc.feed(-1, 3));
  // Pojedynczy impuls w spoczynku jest odrzucany (mniej niż pół ząbka).
  TEST_ASSERT_EQUAL_INT32(0, dc.feed(1, 3));
  TEST_ASSERT_EQUAL_INT32(0, dc.feed(0, 3));
}

void test_detents_two_pulses() {
  DetentCounter dc;
  dc.setPulsesPerDetent(2);
  TEST_ASSERT_EQUAL_INT32(1, dc.feed(2, 0));
  TEST_ASSERT_EQUAL_INT32(-2, dc.feed(-4, 3));
}

void test_decoder_and_detents_with_bouncy_rotation() {
  QuadDecoder dec;
  dec.reset(1, 1);
  DetentCounter dc;
  dc.setPulsesPerDetent(4);
  int32_t steps = 0;
  // Trzy ząbki CW z drganiami na każdym zboczu.
  for (int d = 0; d < 3; ++d) {
    const AB seq[] = {{1, 0}, {1, 1}, {1, 0}, {0, 0}, {1, 0}, {0, 0}, {0, 1},
                      {0, 0}, {0, 1}, {1, 1}, {0, 1}, {1, 1}};
    for (const AB& s : seq) {
      const int8_t p = dec.update(s.a, s.b);
      steps += dc.feed(p, dec.state());
    }
  }
  TEST_ASSERT_EQUAL_INT32(3, steps);
  // Dwa ząbki CCW.
  for (int d = 0; d < 2; ++d) {
    for (const AB& s : kCcwCycle) {
      const int8_t p = dec.update(s.a, s.b);
      steps += dc.feed(p, dec.state());
    }
  }
  TEST_ASSERT_EQUAL_INT32(1, steps);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_full_cycle_cw_gives_four_pulses);
  RUN_TEST(test_full_cycle_ccw_gives_minus_four);
  RUN_TEST(test_bounce_cancels_out);
  RUN_TEST(test_invalid_transition_is_ignored);
  RUN_TEST(test_detents_four_pulses);
  RUN_TEST(test_detents_resync_at_rest);
  RUN_TEST(test_detents_two_pulses);
  RUN_TEST(test_decoder_and_detents_with_bouncy_rotation);
  return UNITY_END();
}
