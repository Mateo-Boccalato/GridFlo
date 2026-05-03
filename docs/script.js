const examples = {
  hello: {
    code: `*"grid"──[upper]──┐
                  [+]──[trim]──< output:value
*"flo"──[upper]──┘`,
    command: `python gridflow.py run "sample programs/hello.gf"`,
    output: `output = 'GRIDFLO'`,
  },
  shout: {
    code: `plate shout:
text:value >──[trim]──[upper]──[!]──< out:value
end

message:value >──[shout]──< result:value`,
    command: `python gridflow.py run "sample programs/shout.gf" message=" hello "`,
    output: `result = 'HELLO!'`,
  },
  fizzbuzz: {
    code: `plate fizzbuzzItem:
i:value >──[%15]──[?=0]──?──[const:FizzBuzz]──< out:value
                         │
                         [%3]──[?=0]──?──[const:Fizz]──< out:value
                                       │
                                       [%5]──[?=0]──?──[const:Buzz]──< out:value
                                                     │
                                                     [str]──< out:value
end

n:value >──[range]──[map:fizzbuzzItem]──< answer:stream`,
    command: `python gridflow.py run "sample programs/fizzbuzz.gf" n=15`,
    output: `answer = ['1', '2', 'Fizz', '4', 'Buzz', 'Fizz', ...]`,
  },
};

const tabs = document.querySelectorAll("[data-example]");
const codeBlock = document.querySelector("#program-code");
const commandBlock = document.querySelector("#program-command");
const outputBlock = document.querySelector("#program-output");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const selectedExample = examples[tab.dataset.example];

    tabs.forEach((button) => {
      const isSelected = button === tab;
      button.classList.toggle("is-active", isSelected);
      button.setAttribute("aria-selected", String(isSelected));
    });

    codeBlock.textContent = selectedExample.code;
    commandBlock.textContent = selectedExample.command;
    outputBlock.textContent = selectedExample.output;
  });
});
