//
// Created by kier on 2018/11/1.
//

#include "compiler/translater.h"
#include "compiler/option/translator_option.h"

#include "module/menu.h"

namespace ts {
    Translator::Translator(const ComputingDevice &device)
        : m_device(device){

    }

    static Node translate_node(const Node& node,
        std::unordered_map<Node, Node> &ready_map,
        const ComputingDevice &device,
        std::vector<const TranslatorOption*> &options,
        bool output_flag) {

        //check ready map
        auto ready_it = ready_map.find(node);
        if (ready_it != ready_map.end()) {
            return ready_it->second;
        }

        auto translated_node = node;
        for (auto option : options) {
            if (option->translate(device, node, translated_node, output_flag)) {
                break;
            }
        }

        std::vector<Node> translated_inputs;
        auto input_nodes = translated_node.inputs();
        for (auto &input : input_nodes) {
            auto translated_input = translate_node(input, ready_map, device, options, false);
            translated_inputs.emplace_back(translated_input);
        }

        ready_map.insert(std::make_pair(node, translated_node));

        Node::Link(translated_node, translated_inputs);

        return translated_node;
    }

    Module::shared Translator::translate(const Module::shared& module) const {

        //std::cout << "+++++++++++++++++ original graph ++++++++++++++++++++++" << std::endl;
        //plot_graph(std::cout, module->outputs());

        Module::shared new_module;

        Graph temp_graph;
        ctx::bind<Graph> _bind_graph(temp_graph);
        //auto temp_graph = ctx::get<Graph>();

        auto options = GetFullTranslateOptions();

        std::vector<Node> traslated_nodes;
        std::unordered_map<Node, Node> ready_map;

        auto output_nodes = module->outputs();
        for (auto & node : output_nodes)
        {
            auto translated_node = translate_node(node, ready_map, m_device, options, true);
            traslated_nodes.emplace_back(translated_node);
        }

        //std::cout << "+++++++++++++++++ translated graph ++++++++++++++++++++++" << std::endl;
        //plot_graph(std::cout, traslated_nodes);

        new_module = Module::Load(temp_graph, traslated_nodes);
        return new_module;
    }
}