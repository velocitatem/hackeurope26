"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function QuestionsPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});

  const questions = [
    {
      title: "What's your GitHub repository?",
      subtitle: "Enter the URL of the repository you want to optimize",
      placeholder: "https://github.com/owner/repo",
      key: "githubRepo",
    },
  ];

  const currentQuestion = questions[currentStep];
  const [value, setValue] = useState(answers[currentStep] || "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    handleNext();
  }

  function handleNext() {
    const newAnswers = { ...answers, [currentStep]: value };
    setAnswers(newAnswers);

    if (currentStep < questions.length - 1) {
      setCurrentStep(currentStep + 1);
      setValue(newAnswers[currentStep + 1] || "");
    } else {
      const params = new URLSearchParams();
      if (newAnswers[0]) params.set("repo", newAnswers[0]);
      router.push(`/training?${params.toString()}`);
    }
  }

  function handleSkip() {
    if (currentStep < questions.length - 1) {
      setCurrentStep(currentStep + 1);
      setValue("");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-xl">
        <div className="mb-8">
          <div className="flex gap-2 mb-4">
            {questions.map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i <= currentStep ? "bg-blue-600" : "bg-gray-200"
                }`}
              />
            ))}
          </div>
          <p className="text-sm text-gray-500">Question {currentStep + 1} of {questions.length}</p>
        </div>

        <h1 className="text-3xl font-bold mb-2">{currentQuestion.title}</h1>
        <p className="text-gray-600 mb-6">{currentQuestion.subtitle}</p>

        <form onSubmit={handleSubmit}>
          <input
            type="url"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={currentQuestion.placeholder}
            className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
        </form>

        <div className="flex gap-4 mt-6">
          <button
            onClick={handleNext}
            className="flex-1 rounded-lg bg-blue-600 px-6 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
          >
            {currentStep < questions.length - 1 ? "Next" : "Get Started"}
          </button>
          {currentStep < questions.length - 1 && (
            <button
              onClick={handleSkip}
              className="px-6 py-3 text-base font-medium text-gray-600 hover:text-gray-800"
            >
              Skip
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
