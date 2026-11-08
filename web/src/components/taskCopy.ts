export const taskQuestions: Record<string, string> = {
  "CS-U1": "Can a model tell what a customer contacted support about?",
  "CS-U2": "How does customer sentiment relate to satisfaction?",
  "CS-U3": "What are the most common reasons customers contact support?",
  "CS-U4": "How long do calls take for each contact reason?",
  "CS-U5": "Can we keep ordinary words in the call text?",
  "CS-U6": "How many contacts come through each channel and language?",
  "CS-U7": "How often is an issue solved on the first contact for each reason?",
};

export function taskQuestion(id: string, fallback?: string) {
  return taskQuestions[id] ?? fallback ?? id;
}
